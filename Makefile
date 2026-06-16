frontend:
	cd base_frontend && npm ci && npm run build

dev-api:
	uv run --cache-dir .uv-cache advogado-api

dev-frontend:
	cd base_frontend && npm run dev

dev:
	$(MAKE) -j2 dev-api dev-frontend
