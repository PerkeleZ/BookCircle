# Kubernetes (пример манифестов)

Манифесты — стартовая точка для кластера; в этом репозитории они **не применялись** (проверена только корректность YAML).
Перед применением: соберите и опубликуйте образ, замените `bookcircle:latest`, домен в `ingress.yaml`, заполните `secret.example.yaml`.
Рекомендуется управляемый PostgreSQL и Redis (хосты задаются в ConfigMap/Secret).

```bash
kubectl create namespace bookcircle
kubectl -n bookcircle apply -f secret.example.yaml -f configmap.yaml
kubectl -n bookcircle apply -f migrate-job.yaml && kubectl -n bookcircle wait --for=condition=complete job/migrate --timeout=300s
kubectl -n bookcircle apply -f web.yaml -f worker.yaml -f beat.yaml -f ingress.yaml
```
