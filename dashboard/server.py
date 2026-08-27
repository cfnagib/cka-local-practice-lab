#!/usr/bin/env python3
import asyncio, json, os, pathlib, pty, re, shlex, subprocess, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = ROOT / "lab"
QUESTION_ROOT = ROOT / "CKA-PREP"
PORT = int(os.environ.get("CKA_DASHBOARD_PORT", "8790"))
WS_PORT = int(os.environ.get("CKA_TERMINAL_PORT", "8791"))
TAILSCALE_IP = os.environ.get("CKA_TAILSCALE_IP", "").strip()
LISTEN_HOSTS = ["127.0.0.1"] + ([TAILSCALE_IP] if TAILSCALE_IP else [])
STATE_DIR = pathlib.Path(os.environ.get("XDG_STATE_HOME", pathlib.Path.home() / ".local/state")) / "cka-local-practice"
STATE_FILE = STATE_DIR / "progress.json"
QPA_WARNING = re.compile(r"qt\.qpa\.services:.*?(?:\n.*?/root\"\)\n?)?", re.DOTALL)
START_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()

def lab_config(key, fallback):
    config = LAB / "config.env"
    if not config.exists():
        return fallback
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s" "${!2}"', "bash", str(config), key],
        text=True,
        capture_output=True,
    )
    return result.stdout or fallback

SSH_USER = lab_config("SSH_USER", os.environ.get("USER", "cfnagib"))
BASE_IP = lab_config("BASE_IP", "192.168.122.40")
CONTROL_IP = lab_config("CONTROL_IP", "192.168.122.63")

def run_lab_script(name, *args):
    command = shlex.join([str(LAB / "scripts" / name), *args])
    return subprocess.run(["sg", "libvirt", "-c", command], cwd=LAB, text=True, capture_output=True)

def valid_question(n):
    return n.isdigit() and 1 <= int(n) <= 17 and question_file(int(n)) is not None

def load_progress():
    with STATE_LOCK:
        try:
            return json.loads(STATE_FILE.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {"questions": {}, "active": {}}

def save_progress(progress):
    with STATE_LOCK:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        temp = STATE_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(progress, indent=2, sort_keys=True))
        temp.replace(STATE_FILE)

def begin_attempt(n):
    progress = load_progress()
    key = str(n)
    record = progress["questions"].setdefault(key, {"attempts": 0, "solved": False, "events": []})
    record["attempts"] += 1
    progress["active"] = {"question": n, "started_at": int(time.time())}
    save_progress(progress)

def record_command(n, command):
    command = command.strip()
    if not command or len(command) > 4000:
        return
    progress = load_progress()
    record = progress["questions"].setdefault(str(n), {"attempts": 0, "solved": False, "events": []})
    events = record.setdefault("events", [])
    events.append({"type": "command", "at": int(time.time()), "command": command})
    record["events"] = events[-500:]
    save_progress(progress)

def finish_validation(n, passed, output):
    progress = load_progress()
    key = str(n)
    record = progress["questions"].setdefault(key, {"attempts": 0, "solved": False, "events": []})
    active = progress.get("active", {})
    elapsed = max(0, int(time.time()) - int(active.get("started_at", time.time()))) if active.get("question") == n else None
    record["last_validation_passed"] = passed
    if elapsed is not None:
        record["last_time_seconds"] = elapsed
    if passed:
        record["solved"] = True
        record["solved_at"] = int(time.time())
        if elapsed is not None:
            best = record.get("best_time_seconds")
            record["best_time_seconds"] = elapsed if best is None else min(best, elapsed)
    events = record.setdefault("events", [])
    events.append({"type": "validation", "at": int(time.time()), "passed": passed, "output": output[-12000:]})
    record["events"] = events[-500:]
    save_progress(progress)
    return progress

def question_hint(n, level):
    notes = QUESTION_ROOT / f"Question-{n}" / "SolutionNotes.bash"
    if not notes.exists():
        return "No hint is available for this question. Use the relevant command help and official documentation."
    lines = [line.removeprefix("#").strip() for line in notes.read_text(errors="replace").splitlines()]
    lines = [line for line in lines if line and not line.startswith("!")]
    if not lines:
        return "No hint is available for this question. Use the relevant command help and official documentation."
    chunk = 3
    start = max(0, (level - 1) * chunk)
    selection = lines[start:start + chunk]
    return "\n".join(selection) if selection else "No further hints are available."

def remote_check(script, ip=CONTROL_IP):
    try:
        result = subprocess.run([
            "ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{ip}",
            f"bash -lc {shlex.quote(script)}",
        ], text=True, capture_output=True, timeout=20)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False

def remote_checks(scripts, ip=CONTROL_IP):
    """Evaluate all hint predicates through one SSH session.

    A button click must not open one SSH connection per learning step: that made a
    hint look frozen whenever the VM was starting. Each predicate prints one
    machine-readable result line, while any command errors remain hidden.
    """
    payload = "set +e\n" + "\n".join(
        f"if {{ {script}; }} >/dev/null 2>&1; then echo 1; else echo 0; fi"
        for script in scripts
    ) + "\n"
    try:
        result = subprocess.run([
            "ssh", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{ip}", "bash -s",
        ], input=payload, text=True, capture_output=True, timeout=25)
        values = [line.strip() == "1" for line in result.stdout.splitlines()]
        return values if len(values) == len(scripts) else [False] * len(scripts)
    except (subprocess.TimeoutExpired, OSError):
        return [False] * len(scripts)

def guided_hint_state(n):
    """State-aware teaching hints for every local task.

    Hints describe the next outcome and how to reason about it. They intentionally
    do not paste a complete command or solution into the terminal.
    """
    specs = {
        1: [
            ("Add the chart repository", "Read item 1 literally: add the repository name and URL from the task, then confirm it is in the Helm repository list.", "helm repo list | awk '$1 == \"argocd\" && $2 == \"https://argoproj.github.io/argo-helm\" {f=1} END {exit !f}'"),
            ("Render the chart", "Item 2 asks for rendered YAML, not a deployed release. Find the Helm template command and its chart-version and namespace flags.", "sudo test -s /root/argo-helm.yaml"),
            ("Exclude CRDs and verify", "Inspect chart values for the CRD-installation setting, render again with it disabled, then check the exact required output path before Validate.", "sudo test -s /root/argo-helm.yaml && sudo grep -q 'app.kubernetes.io/managed-by: Helm' /root/argo-helm.yaml && ! sudo grep -q '^kind: CustomResourceDefinition$' /root/argo-helm.yaml"),
        ],
        2: [
            ("Create shared log storage", "Two containers do not share files by default. Add one Pod volume and mount it at the requested log directory in the existing main container.", "kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.volumes[*].name}' | grep -q . && kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.containers[0].volumeMounts[*].mountPath}' | grep -q '/var/log'"),
            ("Add the sidecar", "Add a second container with the exact name and image from the task. Its long-running command must follow the requested log file on the shared mount.", "kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.containers[?(@.name==\"sidecar\")].image}' | grep -qx 'busybox:stable'"),
            ("Verify the shared mount", "Inspect the Deployment YAML: both containers need the requested mount, and the sidecar command must target wordpress.log. Then Validate.", "kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.containers[?(@.name==\"sidecar\")].volumeMounts[*].mountPath}' | grep -q '/var/log' && kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.containers[?(@.name==\"sidecar\")].command[*]}' | grep -q 'wordpress.log'"),
        ],
        3: [
            ("Create the HTTPS Gateway", "Inspect the old Ingress, TLS secret, Service, and GatewayClass. Create the requested Gateway reproducing HTTPS hostname, listener port, and certificate reference.", "kubectl get gateway web-gateway -n web-app >/dev/null"),
            ("Create the HTTPRoute", "Create the requested route with the same hostname and backend behaviour as the old Ingress. Check the Service name and port instead of guessing.", "kubectl get httproute web-route -n web-app >/dev/null"),
            ("Compare the migrated behaviour", "Verify Gateway class, hostname, TLS secret, route hostname, backend Service, and port against the original Ingress. Then Validate.", "test \"$(kubectl get gateway web-gateway -n web-app -o jsonpath='{.spec.gatewayClassName}')\" = nginx-class && test \"$(kubectl get httproute web-route -n web-app -o jsonpath='{.spec.rules[0].backendRefs[0].name}')\" = web-service"),
        ],
        4: [
            ("Scale down first", "Scale WordPress to zero before changing its Pod template. This gives you a clean point to update resource settings.", "test \"$(kubectl get deploy wordpress -o jsonpath='{.spec.replicas}')\" = 0"),
            ("Set matching resource budgets", "Read node allocatable capacity, reserve safe overhead, and calculate a fair per-Pod budget. Apply exactly the same requests and limits to both init and main containers.", "kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}' | grep -q . && kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.initContainers[0].resources.requests.cpu}' | grep -q ."),
            ("Restore the workload", "Scale back to three replicas. Confirm ready replicas are three and that the init and main CPU request values match before Validate.", "test \"$(kubectl get deploy wordpress -o jsonpath='{.spec.replicas}')\" = 3 && test \"$(kubectl get deploy wordpress -o jsonpath='{.status.readyReplicas}')\" = 3 && test \"$(kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}')\" = \"$(kubectl get deploy wordpress -o jsonpath='{.spec.template.spec.initContainers[0].resources.requests.cpu}')\""),
        ],
        5: [
            ("Create the non-default class", "Create local-storage with the requested provisioner. Check StorageClass documentation for Kubernetes' accepted delayed-binding enum; the task wording has a typo.", "kubectl get sc local-storage >/dev/null"),
            ("Check the class settings", "Inspect provisioner and binding mode before making anything default. Do not alter workloads or PVCs.", "test \"$(kubectl get sc local-storage -o jsonpath='{.provisioner}')\" = rancher.io/local-path && test \"$(kubectl get sc local-storage -o jsonpath='{.volumeBindingMode}')\" = WaitForFirstConsumer"),
            ("Make it the only default", "Default status is an annotation. Set it on local-storage and remove it from every other class, then list all defaults and Validate.", "test \"$(kubectl get sc -o jsonpath='{range .items[*]}{.metadata.name}{\"=\"}{.metadata.annotations.storageclass\\.kubernetes\\.io/is-default-class}{\"\\n\"}{end}' | awk -F= '$2==\"true\"{print $1}' | wc -l)\" = 1 && test \"$(kubectl get sc local-storage -o jsonpath='{.metadata.annotations.storageclass\\.kubernetes\\.io/is-default-class}')\" = true"),
        ],
        6: [
            ("Calculate the reference value", "List user-defined PriorityClasses, exclude Kubernetes system classes, and calculate one less than the largest value.", "kubectl get priorityclass -o name | grep -q priorityclass"),
            ("Create high-priority", "Create the new class with that exact calculated integer. Keep it for user workloads rather than making it a global default.", "kubectl get priorityclass high-priority >/dev/null"),
            ("Assign it and verify", "Set the Deployment Pod template's priorityClassName. Recalculate the expected value from the live class list and compare it before Validate.", "test \"$(kubectl get deploy busybox-logger -n priority -o jsonpath='{.spec.template.spec.priorityClassName}')\" = high-priority && highest=$(kubectl get priorityclass -o jsonpath='{range .items[*]}{.metadata.name}{\"=\"}{.value}{\"\\n\"}{end}' | grep -vE 'system-cluster-critical|system-node-critical|high-priority' | awk -F= '{print $2}' | sort -nr | head -1); test \"$(kubectl get priorityclass high-priority -o jsonpath='{.value}')\" = \"$((highest-1))\""),
        ],
        7: [
            ("Create the NodePort Service", "Inspect the deployment labels and its port first. Create the named Service in the correct namespace with the requested Service port and type.", "kubectl get svc echo-service -n echo-sound >/dev/null"),
            ("Create the Ingress rule", "Create the named Ingress with the exact host and path, routing to the new Service on its Service port.", "kubectl get ingress echo -n echo-sound >/dev/null"),
            ("Verify both entry points", "Check NodePort assignment and endpoints, then inspect the Ingress backend, host, and path. Then Validate.", "test \"$(kubectl get svc echo-service -n echo-sound -o jsonpath='{.spec.type}')\" = NodePort && test \"$(kubectl get ingress echo -n echo-sound -o jsonpath='{.spec.rules[0].http.paths[0].backend.service.name}')\" = echo-service"),
        ],
        8: [
            ("Save the CRD list", "Use kubectl discovery to list CRDs, filter the cert-manager ones, and save the output to the exact absolute file path.", "sudo test -s /root/resources.yaml && sudo grep -q 'cert-manager.io' /root/resources.yaml"),
            ("Discover the field documentation", "Use kubectl's built-in explanation command for the Certificate custom resource. Search for spec.subject rather than using a web article.", "kubectl get crd certificates.cert-manager.io >/dev/null"),
            ("Save and verify field documentation", "Save the relevant documentation to the second required absolute path. It must contain meaningful subject-field details, then Validate.", "sudo test -s /root/subject.yaml && sudo grep -Eiq 'subject' /root/subject.yaml && sudo grep -Eiq 'commonName|organizations|countries|localities' /root/subject.yaml"),
        ],
        9: [
            ("Compare all candidate policies", "Read every YAML file. Compare Pod selector, source namespace, source Pod selector, and port; do not choose based on the filename.", "sudo test \"$(find /root/network-policies -type f | wc -l)\" -ge 3"),
            ("Apply only the least-permissive policy", "Choose the rule that permits frontend Pods to backend Pods on only the required port. Avoid candidates that permit all traffic or an IP range.", "kubectl get networkpolicy policy-z -n backend >/dev/null"),
            ("Verify the live restrictions", "Inspect the applied policy and check that broad candidates were not applied. Validate after source namespace, Pod label, and port are all restricted.", "test \"$(kubectl get networkpolicy policy-z -n backend -o jsonpath='{.spec.ingress[0].ports[0].port}')\" = 80 && ! kubectl get networkpolicy policy-x -n backend >/dev/null 2>&1 && ! kubectl get networkpolicy policy-y -n backend >/dev/null 2>&1"),
        ],
        10: [
            ("Create the HPA target", "Confirm the existing Deployment and its CPU request, then create the named HPA in the stated namespace with its required replica range and CPU target.", "kubectl get hpa apache-server -n autoscale >/dev/null"),
            ("Add scale-down behaviour", "The 30-second setting belongs in the HPA behaviour block. Use API documentation or a generated HPA manifest to find its exact nesting.", "kubectl get hpa apache-server -n autoscale -o jsonpath='{.spec.behavior.scaleDown.stabilizationWindowSeconds}' | grep -qx 30"),
            ("Verify the live HPA", "Inspect target, minimum, maximum, CPU metric, and behaviour. Every requested field must be present before Validate.", "test \"$(kubectl get hpa apache-server -n autoscale -o jsonpath='{.spec.scaleTargetRef.name}')\" = apache-deployment && test \"$(kubectl get hpa apache-server -n autoscale -o jsonpath='{.spec.maxReplicas}')\" = 4 && test \"$(kubectl get hpa apache-server -n autoscale -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')\" = 50"),
        ],
        11: [
            ("Choose against every requirement", "Compare both candidates with all requirements, especially network-policy enforcement. Basic Pod networking alone is not enough.", "kubectl get nodes >/dev/null"),
            ("Apply the pinned CNI manifest", "Use the exact requested version and manifest for your chosen CNI. Wait for controller and node components to appear.", "kubectl get daemonset calico-node -n kube-system >/dev/null 2>&1 || kubectl get daemonset kube-flannel-ds -n kube-flannel >/dev/null 2>&1"),
            ("Verify networking and policy support", "All nodes must be Ready. Because policy enforcement is required, confirm the selected CNI's policy components are running before Validate.", "test \"$(kubectl get nodes --no-headers | awk '$2==\"Ready\"{n++} END{print n+0}')\" -ge 3 && kubectl get daemonset calico-node -n kube-system >/dev/null 2>&1"),
        ],
        12: [
            ("Inspect retained storage", "Confirm the namespace and the single retained PV. Read capacity, access mode, storage class, and binding state before recreating the claim.", "test \"$(kubectl get pv --no-headers | wc -l)\" = 1"),
            ("Recreate the PVC", "Create the named claim in mariadb with the exact access mode and storage size. Ensure it binds to the retained PV.", "kubectl get pvc mariadb -n mariadb >/dev/null"),
            ("Connect the supplied Deployment file", "Edit the provided file so the Pod uses the new claim. Preserve the database configuration, apply it, and wait for matching ready and desired replicas.", "grep -q 'claimName: mariadb' ~/mariadb-deploy.yaml && test \"$(kubectl get pvc mariadb -n mariadb -o jsonpath='{.status.phase}')\" = Bound && test \"$(kubectl get deploy mariadb -n mariadb -o jsonpath='{.status.readyReplicas}')\" = \"$(kubectl get deploy mariadb -n mariadb -o jsonpath='{.spec.replicas}')\""),
        ],
        13: [
            ("Install the supplied package", "Use the local Debian package path from the task. Do not replace it with a downloaded version; resolve any package-manager issue first.", "dpkg -l | awk '$2 == \"cri-dockerd\" {f=1} END {exit !f}'"),
            ("Enable and start the service", "Check the installed unit name, then make the CRI service active now and enabled across reboots.", "systemctl is-enabled cri-docker >/dev/null 2>&1 && systemctl is-active cri-docker >/dev/null 2>&1"),
            ("Set and verify kernel networking values", "Load any needed bridge module and set all four sysctl values from the task. Check live values individually, then Validate.", "lsmod | grep -qw br_netfilter && test \"$(sysctl -n net.bridge.bridge-nf-call-iptables 2>/dev/null)\" = 1 && test \"$(sysctl -n net.ipv6.conf.all.forwarding 2>/dev/null)\" = 1 && test \"$(sysctl -n net.ipv4.ip_forward 2>/dev/null)\" = 1 && test \"$(sysctl -n net.netfilter.nf_conntrack_max 2>/dev/null)\" = 131072"),
        ],
        14: [
            ("Identify the broken endpoint", "The task identifies an external etcd client endpoint using a peer port. Inspect the kube-apiserver static Pod manifest and logs before changing anything.", "sudo grep -q -- '--etcd-servers' /etc/kubernetes/manifests/kube-apiserver.yaml"),
            ("Correct the client port", "Change only the etcd endpoint from the peer port to the client port, then let kubelet recreate the static Pod.", "sudo grep -q ':2379' /etc/kubernetes/manifests/kube-apiserver.yaml && ! sudo grep -q ':2380' /etc/kubernetes/manifests/kube-apiserver.yaml"),
            ("Verify API recovery", "Wait for the static apiserver to become healthy and confirm kubectl can contact the API again. Do not restart unrelated components.", "sudo grep -q ':2379' /etc/kubernetes/manifests/kube-apiserver.yaml && kubectl get nodes >/dev/null 2>&1"),
        ],
        15: [
            ("Apply the exact taint", "Set the specified key, value, and NoSchedule effect on cka-worker1. Inspect the node afterward; do not rely only on command success text.", "test \"$(kubectl get node cka-worker1 -o jsonpath='{.spec.taints[?(@.key==\"PERMISSION\")].value}')\" = granted && test \"$(kubectl get node cka-worker1 -o jsonpath='{.spec.taints[?(@.key==\"PERMISSION\")].effect}')\" = NoSchedule"),
            ("Create a matching workload Pod", "Build a Pod spec with a toleration matching all taint fields and scheduling intent for cka-worker1.", "kubectl get pods -A -o json | jq -e '.items[] | select(.spec.nodeName==\"cka-worker1\") | select(.metadata.namespace != \"kube-system\") | select(any(.spec.tolerations[]?; .key==\"PERMISSION\" and .value==\"granted\" and .effect==\"NoSchedule\"))' >/dev/null"),
            ("Verify placement", "Check the workload Pod's node assignment and live toleration. It must not be an existing system Pod. Then Validate.", "kubectl get pods -A -o wide | awk '$8==\"cka-worker1\" && $1 != \"kube-system\" {f=1} END{exit !f}'"),
        ],
        16: [
            ("Declare the container port", "Edit the Deployment Pod template: port 80 needs the required name and TCP protocol. This is separate from creating a Service.", "kubectl get deploy nodeport-deployment -n relative -o yaml | grep -q 'containerPort: 80' && kubectl get deploy nodeport-deployment -n relative -o yaml | grep -q 'name: http'"),
            ("Create the fixed NodePort Service", "Create the named Service in the same namespace with the requested Service port, target port, protocol, and fixed NodePort value.", "kubectl get svc nodeport-service -n relative >/dev/null"),
            ("Verify service-to-Pod connectivity", "Inspect the selector and endpoints. Confirm fixed NodePort 30080 and that the Service exposes Pod addresses, then Validate.", "test \"$(kubectl get svc nodeport-service -n relative -o jsonpath='{.spec.type}')\" = NodePort && test \"$(kubectl get svc nodeport-service -n relative -o jsonpath='{.spec.ports[0].nodePort}')\" = 30080 && kubectl get endpoints nodeport-service -n relative -o jsonpath='{.subsets[*].addresses[*].ip}' | grep -q ."),
        ],
        17: [
            ("Locate the TLS setting", "Inspect the ConfigMap and how it is mounted by nginx. Identify the precise TLS protocol directive; do not overwrite unrelated configuration.", "kubectl get configmap nginx-config -n nginx-static >/dev/null && kubectl get svc nginx-service -n nginx-static >/dev/null"),
            ("Restrict nginx to TLS 1.3", "Edit only the protocol setting, then roll the workload if necessary so nginx receives the changed ConfigMap.", "kubectl get configmap nginx-config -n nginx-static -o jsonpath='{.data.nginx\\.conf}' | grep -q 'ssl_protocols TLSv1.3;'"),
            ("Map and test the hostname", "Add the Service IP and exact hostname to /etc/hosts on the test machine. TLS 1.2 must fail while TLS 1.3 succeeds, then Validate.", "grep -Eq '^[[:space:]]*[0-9.]+[[:space:]]+ckaquestion\\.k8s\\.local([[:space:]]|$)' /etc/hosts && ! curl -sk --connect-timeout 5 --tls-max 1.2 https://ckaquestion.k8s.local >/dev/null 2>&1 && curl -sk --connect-timeout 5 --tlsv1.3 https://ckaquestion.k8s.local >/dev/null 2>&1"),
        ],
    }
    complete = remote_checks([check for _, _, check in specs[n]])
    return {"available": True, "steps": [
        {"title": title, "text": text, "complete": is_complete}
        for (title, text, _), is_complete in zip(specs[n], complete)
    ]}

def run_validation(n):
    remote = f"bash /tmp/cka-question-{n}/validate.sh"
    return subprocess.run([
        "ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{CONTROL_IP}", remote,
    ], text=True, capture_output=True, timeout=90)

def parse_question(n):
    f = question_file(n)
    if not f:
        return None
    lines = f.read_text(errors="replace").splitlines()
    title = f"Question {n}"
    body = []
    video_url = None
    for raw in lines:
        line = raw.removeprefix("#").lstrip()
        if raw.startswith("# Question "):
            title = f"Question {n} · {line.removeprefix('Question ')}"
        elif line in {"Task", "Video link"}:
            continue
        elif line.startswith("https://youtu.be/"):
            video_url = line
        else:
            body.append(line)
    return {"number": n, "title": title, "text": "\n".join(body).strip(), "video_url": video_url, "target_host": "controlplane"}

def question_file(n):
    d = QUESTION_ROOT / f"Question-{n}"
    return next((d / x for x in ("Questions.bash", "Question.bash") if (d / x).exists()), None)

class Handler(SimpleHTTPRequestHandler):
    def respond_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/api/start/"):
            n = self.path.rsplit("/", 1)[-1]
            if not valid_question(n):
                return self.respond_json({"ok": False, "output": "Question not found."}, 404)
            if not START_LOCK.acquire(blocking=False):
                return self.respond_json({"ok": False, "output": "Another question is still being prepared. Please wait."}, 409)
            try:
                result = run_lab_script("reset-question.sh")
                if result.returncode == 0:
                    result = run_lab_script("run-question.sh", n)
                if result.returncode == 0:
                    begin_attempt(int(n))
                response = {"ok": result.returncode == 0, "output": result.stdout + result.stderr}
            finally:
                START_LOCK.release()
            return self.respond_json(response)
        if self.path.startswith("/api/validate/"):
            n = self.path.rsplit("/", 1)[-1]
            if not valid_question(n):
                return self.respond_json({"ok": False, "output": "Question not found."}, 404)
            try:
                result = run_validation(int(n))
                output = result.stdout + result.stderr
                if result.returncode == 255 and "ssh:" in output:
                    return self.respond_json({"ok": False, "environment_error": True, "output": "The practice VM is unavailable. Reset the question and try again."})
                passed = result.returncode == 0
                progress = finish_validation(int(n), passed, output)
                return self.respond_json({"ok": passed, "output": output, "progress": progress})
            except subprocess.TimeoutExpired:
                return self.respond_json({"ok": False, "output": "Validation timed out. Reset the question and try again."})
        if self.path.startswith("/api/activity/"):
            n = self.path.rsplit("/", 1)[-1]
            if not valid_question(n):
                return self.respond_json({"ok": False, "output": "Question not found."}, 404)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                record_command(int(n), str(payload.get("command", "")))
                return self.respond_json({"ok": True})
            except (ValueError, json.JSONDecodeError):
                return self.respond_json({"ok": False, "output": "Invalid activity data."}, 400)
        self.send_error(404)
    def do_GET(self):
        if self.path.startswith("/api/question/"):
            n = self.path.rsplit("/", 1)[-1]
            data = parse_question(n)
            if data:
                return self.respond_json(data)
        if self.path == "/api/progress":
            return self.respond_json(load_progress())
        if self.path.startswith("/api/review/"):
            n = self.path.rsplit("/", 1)[-1]
            if valid_question(n):
                return self.respond_json(load_progress().get("questions", {}).get(n, {"attempts": 0, "solved": False, "events": []}))
        if self.path.startswith("/api/hint/"):
            parts = self.path.strip("/").split("/")
            if len(parts) == 4 and valid_question(parts[2]) and parts[3].isdigit():
                return self.respond_json({"hint": question_hint(int(parts[2]), max(1, int(parts[3])) )})
        if self.path.startswith("/api/guided-hint/"):
            n = self.path.rsplit("/", 1)[-1]
            if valid_question(n):
                return self.respond_json(guided_hint_state(int(n)))
        return super().do_GET()
    def log_message(self, *_): pass

async def terminal(ws):
    master, slave = pty.openpty()
    proc = subprocess.Popen(["ssh", "-tt", "-o", "LogLevel=ERROR", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{BASE_IP}", "bash -i"], stdin=slave, stdout=slave, stderr=slave, env={**os.environ, "TERM": "xterm-256color", "QT_QPA_PLATFORM": "offscreen"})
    os.close(slave)
    loop = asyncio.get_running_loop()
    async def reader():
        while proc.poll() is None:
            try:
                data = await loop.run_in_executor(None, os.read, master, 4096)
                if data:
                    clean = QPA_WARNING.sub("", data.decode(errors="replace"))
                    if clean: await ws.send(clean)
            except (OSError, websockets.exceptions.ConnectionClosed): break
    task = asyncio.create_task(reader())
    try:
        async for msg in ws:
            if isinstance(msg, str): os.write(master, msg.encode())
    finally:
        task.cancel(); proc.terminate(); os.close(master)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

async def main():
    websocket_servers = [await websockets.serve(terminal, host, WS_PORT) for host in LISTEN_HOSTS]
    for host in LISTEN_HOSTS:
        print(f"Dashboard: http://{host}:{PORT}")
    try:
        await asyncio.Future()
    finally:
        for server in websocket_servers:
            server.close()
            await server.wait_closed()

if __name__ == "__main__":
    os.chdir(pathlib.Path(__file__).parent / "static")
    for host in LISTEN_HOSTS:
        http = ThreadingHTTPServer((host, PORT), Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
    asyncio.run(main())
