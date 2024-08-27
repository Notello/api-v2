FROM neo4j:4.4

COPY backup-script.sh /backup-script.sh
RUN chmod +x /backup-script.sh

CMD ["/backup-script.sh"]