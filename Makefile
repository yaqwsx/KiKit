

.PHONY: doc clean package release

all: doc package

doc: doc/panelization.md

doc/panelization.md: kikit/panelize.py scripts/panelizeDoc.py
	PYTHONPATH=`pwd` python3 scripts/panelizeDoc.py > $@

package:
	python3 setup.py sdist bdist_wheel

install: package
	pip3 install --no-deps --force dist/KiKit-0.1.0-py3-none-any.whl

release: package
	twine upload dist/*

clean:
	rm -rf dist build