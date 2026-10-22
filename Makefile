PYTHON ?= python

.PHONY: data
data:
	$(PYTHON) -m pdxmodel.data
