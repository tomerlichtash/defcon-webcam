VENV := .venv/bin/activate
PORT := 8081
PID_WEB   = $(shell lsof -ti:$(PORT) 2>/dev/null)
PID_ALERT = $(shell pgrep -f 'python3 bin/mjpg-alert' 2>/dev/null)

.PHONY: start stop restart status test db-reset db-shell db-populate fmt

start:
	@if [ -n "$(PID_WEB)" ]; then echo "Web already running (PID $(PID_WEB))"; exit 1; fi
	@echo "Starting alert service..."
	@source $(VENV) && python3 bin/mjpg-alert &
	@sleep 1
	@echo "Starting web server..."
	source $(VENV) && python3 bin/mjpg-web

stop:
	@if [ -n "$(PID_ALERT)" ]; then kill $(PID_ALERT) && echo "Alert stopped (PID $(PID_ALERT))"; fi
	@if [ -n "$(PID_WEB)" ]; then kill $(PID_WEB) && echo "Web stopped (PID $(PID_WEB))"; fi
	@if [ -z "$(PID_ALERT)" ] && [ -z "$(PID_WEB)" ]; then echo "Not running"; fi

restart: stop
	@sleep 1
	@$(MAKE) start

status:
	@if [ -n "$(PID)" ]; then echo "Running (PID $(PID))"; else echo "Not running"; fi

db-reset:
	@source $(VENV) && python3 -c "from lib.event_log import reset_db, init_db; reset_db(); init_db(); print('Event log reset')"

db-shell:
	@sqlite3 "$$(python3 -c 'import tempfile, os; print(os.path.join(tempfile.gettempdir(), "mjpg-events.db"))')"

db-populate:
	@source $(VENV) && python3 bin/populate-geo

test:
	@source $(VENV) && python3 -m unittest discover -s tests -v

fmt:
	@npx prettier --write 'static/js/**/*.js' 'static/styles/*.css' 'static/i18n/*.json'
	@source $(VENV) && python3 -m ruff format lib/ bin/
