PYTHON ?= python

.PHONY: data fit
data:
	$(PYTHON) -m pdxmodel.data

fit:
	$(PYTHON) -m pdxmodel.export
