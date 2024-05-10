.DEFAULT_GOAL := all
PIP_INSTALL := pip install --no-cache-dir --upgrade
scale := 1

.PHONY: all
all: build run

.PHONY: build
build:
	docker-compose build

# Runs everything, defaults to 1 replica of batch_transcriber.
# to set higher replicas, set the scale parameter
# e.g. make run scale=2
.PHONY: run
run:
	docker-compose up --scale rabbitmq_client=1 --scale batch_transcriber=$(scale)

.PHONY: clean
clean:
	docker-compose down --rmi all --volumes --timeout 0
	docker-compose rm -fsv


.PHONY: down
down:
	docker-compose down


# Runs everything except rabbitmq_client and batch_transcriber services, which are scaled to 0 by config.
# In a demo, we want the base services up, then show the run-client and run-transcriber targets .
.PHONY: demo
demo: build run-demo

.PHONY: run-demo
run-demo:
	docker-compose up -d

# Start rabbitmq_client
.PHONY: run-client
run-client:
	docker-compose up -d rabbitmq_client --scale rabbitmq_client=1

# Scale transcriber to x replicas
# e.g.: make scale-transcriber scale=n (default is 1)
.PHONY: run-transcriber
run-transcriber:
	docker-compose up -d batch_transcriber --scale batch_transcriber=$(scale)

.PHONY: logs
logs:
	docker-compose logs -f

# Development mode maps source tree into the containers for ease of development
# Also starts 1 replica rabbitmq_client and batch_transcriber.
.PHONY: dev-run
dev-run:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up --scale batch_transcriber=$(scale)

# Start rabbitmq_client
.PHONY: dev-run-client
dev-run-client:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d rabbitmq_client --scale rabbitmq_client=1

# Scale transcriber to x replicas
# e.g.: make scale-transcriber scale=n (default is 1)
.PHONY: dev-run-transcriber
dev-run-transcriber:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d batch_transcriber --scale batch_transcriber=$(scale)


# Install deps locally -- probably best done in a devcontainer.
.PHONY: dev-depends-local
dev-depends-local:
	$(PIP_INSTALL) \
		-r ./callback_server/requirements.txt \
		-r ./rabbitmq_client/requirements.txt \
		-r ./sm_batch_transcriber/requirements.txt


