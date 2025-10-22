run:
	python rumor_mill.py --date today
daily:
	python rumor_mill.py --date $$(date +%F)
docker-build:
	docker build -t rumor-mill:latest .
docker-run:
	docker run --rm -e OPENAI_API_KEY=$$OPENAI_API_KEY rumor-mill:latest
