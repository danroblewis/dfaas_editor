docker build -t danroblewis/dfaas-webide:latest .
docker run --env-file .env -it danroblewis/dfaas-webide:latest
