cp .env.example .env
docker compose up -d
curl http://localhost:8080/version
