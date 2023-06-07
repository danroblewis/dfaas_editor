docker build -t danroblewis/dfaas-webide:latest .
docker run -p 3001:3001 --env-file .env -it danroblewis/dfaas-webide:latest
