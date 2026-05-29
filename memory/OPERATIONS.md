# OPERATIONS

Runtime path:
/opt/automation

API:
systemctl status automation-api
journalctl -u automation-api -f

Daily brief:
systemctl status daily-brief.timer
journalctl -u daily-brief -f

Vault:
/opt/automation/vault

Database:
/opt/automation/data/automation.db
