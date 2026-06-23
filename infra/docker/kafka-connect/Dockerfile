# Custom Kafka Connect image for psql-ranking-poc CDC pipeline.
#
# Uses confluentinc/cp-kafka-connect as the base (it ships confluent-hub),
# then installs both connectors needed for this pipeline:
#
# Plugins installed:
#   - debezium/debezium-connector-postgresql 2.4.2   (CDC source from Cloud SQL)
#   - confluentinc/kafka-connect-elasticsearch 14.0.12 (sink to Elasticsearch)

FROM confluentinc/cp-kafka-connect:7.5.0

RUN confluent-hub install --no-prompt debezium/debezium-connector-postgresql:2.4.2 \
    && confluent-hub install --no-prompt confluentinc/kafka-connect-elasticsearch:latest
