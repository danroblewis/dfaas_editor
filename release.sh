./build.sh
./publish.sh
kubectl get pod  | grep ^dfaas-webide | awk '{print $1}' | while read i; do kubectl delete pod $i & done
