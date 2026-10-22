PYTHON ?= python
TECTONIC ?= tectonic

.PHONY: data fit report
data:
	$(PYTHON) -m pdxmodel.data

fit:
	$(PYTHON) -m pdxmodel.export

report:
	cd report && $(TECTONIC) report.tex --outdir .
