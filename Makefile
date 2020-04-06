

.PHONY: doc

doc: doc/panelization.md

doc/panelization.md: kikit/panelize.py scripts/panelizeDoc.py
	PYTHONPATH=`pwd` python3 scripts/panelizeDoc.py > $@