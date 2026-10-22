PYTHON ?= python

.PHONY: setup data fit report web-data web-build zip all
setup:
	$(PYTHON) -m pip install -e 'analysis[dev]'

data:
	$(PYTHON) -m pdxmodel.data

fit:
	$(PYTHON) -m pdxmodel.export

report:
	$(PYTHON) -m pdxmodel.texcompile

web-data:
	$(PYTHON) -m pdxmodel.deliverables web-data

web-build:
	npm --prefix web ci --no-audit --no-fund
	npm --prefix web run build

zip:
	$(PYTHON) -m pdxmodel.deliverables zip

all: setup data fit report web-data web-build zip
