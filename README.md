# Fluid AI — DevOps Challenge

FastAPI backend + PostgreSQL, deployed to Kubernetes (Kind), with GitHub Actions CI/CD.

## Architecture
- **Backend**: FastAPI (`/health` liveness, `/ready` readiness DB-check, `/items` demo endpoint)
- **Database**: PostgreSQL, credentials via Kubernetes Secret
- **Reliability improvement chosen**: Secret management via HashiCorp Vault (Agent Injector sidecar pattern) — see `VAULT-SETUP.md` for the full why/problem/tradeoff writeup and setup steps.
- Readiness/liveness probes are also implemented (see manifests) and can be discussed as a secondary reliability point.
- **CI/CD**: GitHub Actions builds the image, spins up an ephemeral Kind cluster on the runner, loads the image, applies manifests, waits for rollout, and smoke-tests `/health`.

## Local Setup (run these in order)

### 1. Recreate the Kind cluster with the port mapping
Your existing `devops-challenge` cluster wasn't created with the NodePort mapping needed to hit the service from your host. Recreate it using the provided config:

```bash
kind delete cluster --name devops-challenge
kind create cluster --config kind-config.yaml
kubectl get nodes
```

### 2. Build the backend image locally
```bash
cd app
docker build -t fluid-ai-backend:latest .
cd ..
```

### 3. Load the image into the Kind cluster
Kind clusters can't pull local images from Docker directly — this step pushes it into the cluster's internal image store.
```bash
kind load docker-image fluid-ai-backend:latest --name devops-challenge
```

### 4. Set up Vault, then apply the manifests
Secrets now come from HashiCorp Vault, not a K8s Secret — follow **`VAULT-SETUP.md`** first
(install Vault, write the secret, configure Kubernetes auth). Then:
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/serviceaccounts.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
```

### 5. Watch rollout
```bash
kubectl get pods -n fluid-ai -w
```
Wait until both `postgres-...` and `backend-...` pods show `1/1 Running`. Ctrl+C to stop watching.

### 6. Test it
```bash
curl http://localhost:30080/health
curl http://localhost:30080/ready
curl -X POST http://localhost:30080/items
curl http://localhost:30080/items
```

---

## Intentional Failure Simulation (bad DB env var)

This is the section you demo live and debug on camera.

### Step 1 — Break it
Edit `k8s/backend-deployment.yaml`, change:
```yaml
            - name: DB_HOST
              value: "postgres-service"
```
to:
```yaml
            - name: DB_HOST
              value: "postgres-wrong-service"
```

Apply it:
```bash
kubectl apply -f k8s/backend-deployment.yaml
```

### Step 2 — Show the failure
```bash
kubectl get pods -n fluid-ai
```
Backend pods will show `Running` but **not** `Ready` (e.g. `0/1`) — because the readiness probe on `/ready` is failing (it checks the DB connection).

### Step 3 — Debug live
```bash
kubectl describe pod <backend-pod-name> -n fluid-ai
```
Look at the **Events** section — you'll see `Readiness probe failed`.

```bash
kubectl logs <backend-pod-name> -n fluid-ai
```
You won't see a crash (the app itself is fine) — this is the key diagnostic insight: the **process is alive**, only the **dependency check is failing**. This is exactly why liveness and readiness are separate — a crash-loop would be a different failure mode entirely.

```bash
curl http://localhost:30080/ready
```
This returns `503` with the actual psycopg2 connection error naming the bad host — your root cause.

### Step 4 — Fix it
Revert `DB_HOST` back to `postgres-service` in `k8s/backend-deployment.yaml`, then:
```bash
kubectl apply -f k8s/backend-deployment.yaml
kubectl get pods -n fluid-ai -w
```
Pods return to `1/1 Ready`.

### Narration points for your video
- Symptom: pod `Running` but not `Ready`, service returning connection errors
- Wrong assumption to voice (for authenticity): "is the container crashing?" → check logs → it's not, ruling out a crash-loop
- Real check: `describe pod` events + `/ready` endpoint response → reveals DNS resolution failure for `postgres-wrong-service`
- Root cause: typo'd/incorrect Kubernetes service name in env var
- Fix: correct the env var, reapply, confirm readiness recovers

---

## Tradeoffs / What Would Break at Scale
- **Single Postgres replica**, no persistent volume claim — data is lost on pod restart. Production needs a `StatefulSet` + PVC or a managed DB service.
- **No ingress/TLS** — using NodePort for simplicity. Production needs an Ingress controller + cert-manager.
- **No HPA (autoscaling)** — fixed 2 replicas. Real traffic variability needs a `HorizontalPodAutoscaler`.
- **Secrets in plain `stringData`** — fine for a local demo, but production should use sealed-secrets, External Secrets Operator, or a cloud KMS-backed secret store.
- **CI/CD deploys to an ephemeral cluster**, not the real one — production CI/CD would deploy via GitOps (ArgoCD/Flux) against a persistent cluster with proper rollback and approval gates.
