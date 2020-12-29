

.PHONY: doc clean package release test

all: doc package test

doc: doc/panelization.md doc/examples.md

doc/panelization.md: kikit/panelize.py scripts/panelizeDoc.py
	PYTHONPATH=`pwd` python3 scripts/panelizeDoc.py > $@

doc/examples.md: scripts/exampleDoc.py
	pcbdraw --silent doc/resources/conn.kicad_pcb doc/resources/conn.png
	PYTHONPATH=`pwd` python3 scripts/exampleDoc.py > $@

package:
	rm -f dist/*
	python3 setup.py sdist bdist_wheel

install: package
	pip3 install --no-deps --force dist/*.whl

release: package
	twine upload dist/*

test: build/test $(shell find kikit -type f)
	cd build/test && bats ../../test/system

build/test:
	mkdir -p $@

clean:
	rm -rf dist build