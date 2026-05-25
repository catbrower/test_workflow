TTL = 300                                            # seconds — Redis key TTL and read block timeout
DELETE_ARGS_KEYS = True                              # delete args keys from Redis immediately after reading

NAMESPACE = "swarmopt"                               # Kubernetes namespace all workflow jobs run in
SERVICE_ACCOUNT = "workflow-runner"                  # ServiceAccount that grants jobs permission to create jobs
IMAGE_PULL_POLICY = "Never"                          # Never = use locally loaded images (minikube image load)
REDIS_HOST_DEFAULT = "redis.swarmopt.svc.cluster.local"  # in-cluster Redis hostname
