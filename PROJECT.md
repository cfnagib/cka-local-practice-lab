# CKA Local Exam Lab

## الهدف

بناء بيئة تدريب محلية مجانية ومنظمة لامتحان CKA تعمل على جهاز Kubuntu نفسه، بدون التأثير على النظام الأساسي. بعد إعداد أولي واحد، يفتح المستخدم التطبيق، يختار سؤالًا، يبدأ بيئة جاهزة، يحل داخل Terminal قريب من أسلوب الامتحان، ثم يضغط Reset لإرجاع السؤال لحالته الأصلية.

## تجربة الاستخدام اليومية المستهدفة

```text
تشغيل التطبيق
    ↓
اختيار سؤال CKA
    ↓
Start Lab
    ↓
عرض نص السؤال + Terminal/Remote Desktop
    ↓
حل السؤال
    ↓
Validate
    ↓
Reset Lab أو حفظ التقدم والعودة لاحقًا
```

المستخدم لا يعيد تثبيت Kubernetes أو تجهيز Nodes لكل سؤال.

## العزل والأمان

- Kubuntu الأساسي لا يستضيف kubelet أو etcd الخاصين باللاب.
- Kubernetes يعمل داخل VMs محلية باستخدام KVM/QEMU وlibvirt.
- Snapshot نظيف يُؤخذ بعد تجهيز Cluster.
- كل سؤال يمكن أن يملك snapshot أو reset script مستقلًا.
- أي تجربة تكسر kubelet أو runtime أو systemd يمكن استرجاعها بدون التأثير على الجهاز الأساسي.
- Docker/CK-X الحاليان يظلان منفصلين عن المشروع.

## الأداء والسلاسة

الأولوية أثناء الحل هي استجابة الـ Terminal، لذلك:

- استخدام KVM/QEMU مع libvirt بدل VirtualBox أو Remote Desktop سحابي كلما أمكن.
- استخدام SSD للتخزين؛ وضع ملفات الـ VMs وSnapshots على أسرع قرص متاح.
- تشغيل Terminal محلي من Kubuntu متصل بالـ VMs عبر SSH بدل الاعتماد على واجهة رسومية ثقيلة.
- تخصيص موارد ثابتة وعدم تشغيل أكثر من Cluster تدريب عند الحاجة.
- تخصيص مبدئي مقترح: 3 VMs، كل VM بذاكرة 4–6GB و2 vCPU، مع إبقاء موارد كافية للنظام الأساسي.
- تفعيل virtio للشبكة والقرص، وCPU mode مناسب للمضيف.
- عدم تشغيل Remote Desktop إلا في وضع Mock Exam لمحاكاة الامتحان؛ وضع Learning يستخدم Terminal سريع.
- أخذ snapshots بعد حالات مستقرة، واسترجاع snapshot بدل إعادة إنشاء البيئة.
- قياس زمن استجابة SSH و`kubectl` قبل اعتماد البيئة؛ لا نعتبر المرحلة مكتملة إذا كان Terminal يتأخر أو يعلّق.

## المعمارية المقترحة

### طبقة البيئة

- 3 VMs: `controlplane`, `node01`, `node02`.
- Ubuntu Server داخل VMs.
- Kubernetes مثبت بـ `kubeadm`.
- containerd كـ Container Runtime.
- CNI مناسب للتدريب.
- شبكة داخلية للـ VMs مع اتصال إنترنت اختياري للتثبيت والتحديث.

### طبقة الإدارة

- سكربتات idempotent لإعداد البيئة والتحقق منها.
- أوامر `start`, `stop`, `status`, `snapshot`, `restore`, `reset-question`.
- لا تعتمد الأسئلة على حالة سؤال سابق.
- كل سؤال يملك `setup`, `validate`, و`reset` عند الحاجة.

### طبقة التطبيق

- Dashboard محلي يعرض قائمة الأسئلة والموضوعات والصعوبة.
- صفحة سؤال شبيهة بفكرة الامتحان: نص المهمة، الوقت الاختياري، روابط التوثيق المسموحة، وTerminal.
- أزرار: `Start`, `Validate`, `Reset`, `Show Hint`.
- الحلول لا تظهر تلقائيًا؛ التلميحات تكون تدريجية.
- حفظ حالة التقدم محليًا.

## بنك الأسئلة

المصدر الأساسي:

- [CameronMetcalfe22/CKA-PREP](https://github.com/CameronMetcalfe22/CKA-PREP): 17 سؤالًا مع نص، setup، validation، وملاحظات حل.

مصادر إضافية:

- [chadmcrowell/CKA-Exercises](https://github.com/chadmcrowell/CKA-Exercises)
- [bmuschko/cka-crash-course](https://github.com/bmuschko/cka-crash-course)
- [Kubernetes Tasks](https://kubernetes.io/docs/tasks/)

كل سؤال سيُحوّل إلى صيغة موحدة:

```text
questions/<id>/question.md
questions/<id>/metadata.yaml
questions/<id>/setup.sh
questions/<id>/validate.sh
questions/<id>/reset.sh
questions/<id>/hints.md
questions/<id>/solution-notes.md
```

## مراحل التنفيذ

### المرحلة 1: بيئة محلية قابلة للاسترجاع

- فحص KVM/libvirt ومتطلبات الجهاز.
- إنشاء VMs الثلاثة.
- تثبيت Kubernetes بـ kubeadm.
- أخذ snapshot نظيف.
- تجربة إيقاف وتشغيل واسترجاع البيئة.

### المرحلة 2: سؤال واحد كنموذج

- تحويل Question 1 إلى الصيغة الموحدة.
- تشغيل setup.
- عرض السؤال.
- validate.
- reset وإعادة المحاولة.

### المرحلة 3: بنك الأسئلة

- إضافة الأسئلة السبعة عشر.
- تصنيفها: Architecture, Workloads, Services/Networking, Storage, Troubleshooting.
- إضافة أسئلة node-level مثل kubeadm upgrade وkubelet وcontainerd بصورة منفصلة.

### المرحلة 4: Dashboard

- واجهة محلية بسيطة.
- تشغيل وإيقاف/reset من زر.
- فتح Terminal أو Remote Desktop.
- مؤقت اختياري للتدريب، مع وضع بدون وقت للمذاكرة.

### المرحلة 5: محاكاة الامتحان

- وضع امتحان من 17 مهمة خلال ساعتين.
- لا تظهر الحلول أثناء المحاولة.
- تقرير بالنتيجة ونقاط الضعف.
- Killer.sh يُستخدم لاحقًا فقط لمقارنة واجهة الامتحان الحقيقية.

## تعريف النجاح

يُعتبر النظام جاهزًا عندما يستطيع المستخدم:

1. تشغيل البيئة بأمر أو زر واحد.
2. اختيار سؤال والبدء خلال دقائق.
3. إيقاف الجهاز والعودة في يوم آخر بدون إعادة الإعداد.
4. Reset سؤال واحد دون التأثير على بقية البيئة.
5. تشغيل validate ومعرفة النتيجة.
6. تجربة kubeadm/kubelet/containerd بأمان داخل VMs.
