#!/usr/bin/env bash
set -euo pipefail

INFRA_NS="swarmopt"
REDIS_PORT="6379"        # port Redis listens on inside the cluster (also used locally via port-forward)

echo "==> Building workflow images..."
docker build -t workflow-main:latest       -f functions/main/Dockerfile       .
docker build -t workflow-montecarlo:latest -f functions/montecarlo/Dockerfile .

echo ""
echo "==> Loading images into minikube..."
minikube image load --overwrite=true workflow-main:latest
minikube image load --overwrite=true workflow-montecarlo:latest

echo ""
echo "==> Port-forwarding Redis (localhost:$REDIS_PORT -> redis.$INFRA_NS)..."
kubectl port-forward -n "$INFRA_NS" svc/redis "$REDIS_PORT:$REDIS_PORT" &
PF_PID=$!
trap 'kill "$PF_PID" 2>/dev/null || true' EXIT
sleep 2

WORKFLOW_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
WORKFLOW_NS="workflow-${WORKFLOW_ID: -12}"
REDIS_KEY="montecarlo-main-$WORKFLOW_ID"
RESULT_STREAM="montecarlo-return-$WORKFLOW_ID"
JOB_NAME="workflow-main-${WORKFLOW_ID:0:8}"

echo ""
echo "==> Creating namespace and RBAC: $WORKFLOW_NS"
kubectl create namespace "$WORKFLOW_NS" 2>/dev/null || true
kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: workflow-runner
  namespace: $WORKFLOW_NS
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: workflow-job-creator
  namespace: $WORKFLOW_NS
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: workflow-runner-jobs
  namespace: $WORKFLOW_NS
subjects:
  - kind: ServiceAccount
    name: workflow-runner
    namespace: $WORKFLOW_NS
roleRef:
  kind: Role
  name: workflow-job-creator
  apiGroup: rbac.authorization.k8s.io
EOF

echo ""
echo "==> Writing args: $REDIS_KEY"
redis-cli -p "$REDIS_PORT" SET "$REDIS_KEY" '{"n": 50000, "population_size": 10, "generations": 10}'

echo ""
echo "==> Subscribing to $RESULT_STREAM"
python3 -c "
import redis, json, time
r = redis.Redis(port=int('$REDIS_PORT'), decode_responses=True)
last = '0-0'
deadline = time.time() + 600
while time.time() < deadline:
    res = r.xread({'$RESULT_STREAM': last}, count=10, block=500)
    if res:
        for _, msgs in res:
            for mid, fields in msgs:
                data = json.loads(fields['data'])
                print(json.dumps(data, indent=2), flush=True)
                last = mid
" &
READER_PID=$!

echo ""
echo "==> Creating main job: $JOB_NAME (namespace=$WORKFLOW_NS, workflow_id=$WORKFLOW_ID)"
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $JOB_NAME
  namespace: $WORKFLOW_NS
spec:
  ttlSecondsAfterFinished: 300
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: workflow-runner
      containers:
        - name: main
          image: workflow-main:latest
          imagePullPolicy: Never
          args: ["$REDIS_KEY"]
          env:
            - name: REDIS_HOST
              value: redis.swarmopt.svc.cluster.local
            - name: REDIS_PORT
              value: "6379"
            - name: WORKFLOW_NAMESPACE
              value: "$WORKFLOW_NS"
            - name: WORKFLOW_NAME
              value: montecarlo
            - name: WORKFLOW_ID
              value: "$WORKFLOW_ID"
            - name: INSTANCE_ID
              value: "$WORKFLOW_ID"
EOF

echo ""
echo "==> Waiting for job $JOB_NAME..."
while true; do
    CONDITION=$(kubectl get job/"$JOB_NAME" -n "$WORKFLOW_NS" \
        -o jsonpath='{.status.conditions[?(@.status=="True")].type}' 2>/dev/null)
    POD_LINE=$(kubectl get pods -n "$WORKFLOW_NS" -l "job-name=$JOB_NAME" \
        --no-headers 2>/dev/null | awk '{print $3, $4}' | head -1)
    echo "  [$(date +%H:%M:%S)] job=${CONDITION:-pending} pod=${POD_LINE:-unknown}"
    if echo "$CONDITION" | grep -qi "complete"; then
        echo "==> Job completed."
        break
    elif echo "$CONDITION" | grep -qi "failed"; then
        echo "==> Job FAILED. Logs:"
        kubectl logs -n "$WORKFLOW_NS" -l "job-name=$JOB_NAME" --tail=100 2>/dev/null || true
        kill "$READER_PID" 2>/dev/null || true
        exit 1
    fi
    sleep 3
done

sleep 1
kill "$READER_PID" 2>/dev/null || true

echo ""
echo "==> Stream: $RESULT_STREAM"
redis-cli -p "$REDIS_PORT" XRANGE "$RESULT_STREAM" - +

echo ""
echo "==> Cleaning up namespace $WORKFLOW_NS..."
kubectl delete namespace "$WORKFLOW_NS" --wait=false 2>/dev/null || true
echo "==> Done."
