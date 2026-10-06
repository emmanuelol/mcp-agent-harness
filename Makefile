.PHONY: build test demo audit clean

build:
	docker build -t mcp-agent-harness:latest .

test:
	docker compose run --rm test

demo:
	docker compose up -d harness
	sleep 3
	curl -f -s http://localhost:8000/health
	docker compose down

audit:
	./scripts/audit_image.sh

clean:
	docker compose down --rmi all --volumes --remove-orphans
