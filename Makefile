include .env
export

.PHONY: dummy-vape

dummy-vape:
	VAPE_API_TOKEN=$(VAPE_API_TOKEN) python dummy_vape.py
