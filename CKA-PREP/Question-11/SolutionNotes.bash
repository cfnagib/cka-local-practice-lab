# Calico is specified because the task requires NetworkPolicy enforcement.
# Before applying a CNI manifest, inspect the release documentation for the
# installation sequence and the components that should become ready.
#
# After installation, verify that all nodes are Ready and that Calico's node and
# controller components are running. Do not treat successful manifest submission
# as proof that cluster networking is functional.
