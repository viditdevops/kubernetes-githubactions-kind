# Vault Setup (HashiCorp Vault — Secret Management)

This replaces plain Kubernetes Secrets. No credential ever lives in a YAML file or
`kubectl` history — Vault stores it, and the Vault Agent Injector sidecar fetches it
into each pod at startup only.

**Why this reliability improvement**: a leaked Kubernetes Secret manifest, a `git`
commit, or `kubectl get secret -o yaml` all expose base64 (not encrypted) credentials
by default. Vault centralizes secrets, encrypts at rest, supports rotation and
fine-grained per-app policies (the backend can only read `secret/data/fluid-ai/db`,
nothing else).
**Tradeoff**: extra moving part — Vault itself becomes something that must be running
and unsealed for your app to start at all. Pods will sit stuck if Vault is down or
misconfigured. Dev-mode (used below) is explicitly NOT production-safe: it runs
unsealed, in-memory, with a single root token — fine for this demo, never for real use.

## 1. Install Vault in dev mode via Helm

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update

helm install vault hashicorp/vault \
  --set "server.dev.enabled=true" \
  --set "injector.enabled=true" \
  --namespace vault --create-namespace
```

Wait for pods:
```bash
kubectl get pods -n vault -w
```
You should see `vault-0` (`Running`) and `vault-agent-injector-...` (`Running`).

## 2. Write the DB secret into Vault

```bash
kubectl exec -n vault -it vault-0 -- vault kv put secret/fluid-ai/db \
  host="postgres-service" \
  port="5432" \
  name="appdb" \
  user="appuser" \
  password="apppassword"
```

Verify:
```bash
kubectl exec -n vault -it vault-0 -- vault kv get secret/fluid-ai/db
```

## 3. Enable Kubernetes auth so pods can authenticate to Vault

```bash
kubectl exec -n vault -it vault-0 -- vault auth enable kubernetes

kubectl exec -n vault -it vault-0 -- sh -c '
vault write auth/kubernetes/config \
  kubernetes_host="https://$KUBERNETES_SERVICE_HOST:443"
'
```

## 4. Create a policy scoping access to just this secret path

```bash
kubectl exec -n vault -it vault-0 -- sh -c '
vault policy write fluid-ai-db-policy - <<EOF
path "secret/data/fluid-ai/db" {
  capabilities = ["read"]
}
EOF
'
```

## 5. Bind each ServiceAccount to that policy

```bash
kubectl exec -n vault -it vault-0 -- vault write auth/kubernetes/role/fluid-ai-backend \
  bound_service_account_names=fluid-ai-backend \
  bound_service_account_namespaces=fluid-ai \
  policies=fluid-ai-db-policy \
  ttl=1h

kubectl exec -n vault -it vault-0 -- vault write auth/kubernetes/role/fluid-ai-postgres \
  bound_service_account_names=fluid-ai-postgres \
  bound_service_account_namespaces=fluid-ai \
  policies=fluid-ai-db-policy \
  ttl=1h
```

## 6. Now apply your app manifests (order matters: ServiceAccounts before Deployments)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/serviceaccounts.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
```

Each pod will now show **2/2** containers (your app container + the injected
`vault-agent` sidecar), not 1/1. That second container is the proof, on camera,
that secrets are coming from Vault.

## 7. Verify — prove no secret lives in the cluster's Secret objects

```bash
kubectl get secrets -n fluid-ai
```
You should NOT see a `postgres-secret` object anymore — nothing DB-related here at all.

```bash
kubectl exec -it <backend-pod-name> -n fluid-ai -c backend -- cat /vault/secrets/db-env
```
This shows the rendered file — proving the sidecar wrote it, not a K8s Secret mount.
