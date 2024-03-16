
.SHELLFLAGS += -e

PCM_KIKIT_RESOURCES := $(shell find pcm/kikit -type f -print) \
	$(shell find kikit/resources/graphics -type f -print)
PCM_LIB_RESOURCES :=  $(shell find pcm/kikit-lib -type f -print) \
	$(shell find kikit/resources/graphics -type f -print) \
	$(shell find kikit/resources/kikit.kicad_sym -type f -print) \
	$(shell find kikit/resources/kikit.pretty -type f -print)

.PHONY: doc clean package release test test-system test-unit docker-release

all: doc package test pcm

doc: docs/panelization/python_api.md docs/panelization/examples.md

docs/panelization/python_api.md: kikit/panelize.py scripts/panelizeDoc.py
	PYTHONPATH="$(pwd):${PYTHONPATH}" python3 scripts/panelizeDoc.py > $@

doc/resources/conn.png: docs/resources/conn.kicad_pcb
	pcbdraw plot --silent $< $@
	convert $@ -define png:include-chunk=none $@

docs/panelization/examples.md: scripts/exampleDoc.py docs/resources/conn.png
	PYTHONPATH="$(pwd):${PYTHONPATH}" python3 scripts/exampleDoc.py > $@

package:
	rm -f dist/*
	python3 setup.py sdist bdist_wheel

install: package
	pip3 install --no-deps --force dist/*.whl

release: package
	twine upload dist/*

test: test-system test-unit

test-system: build/test $(shell find kikit -type f)
	cd build/test && bats ../../test/system

test-unit:
	cd test/units && pytest

build/test:
	mkdir -p $@

pcm: pcm-kikit pcm-lib

pcm-kikit: $(PCM_KIKIT_RESOURCES)
	rm -rf build/pcm-kikit build/pcm-kikit.zip
	mkdir -p build/pcm-kikit
	mkdir -p build/pcm-kikit/resources
	cp -r pcm/kikit/* build/pcm-kikit
	find build/pcm-kikit -name "*.pyc" -type f -delete
	cp kikit/resources/graphics/kikitIcon_64x64.png build/pcm-kikit/resources/icon.png
	ls -lah build
	scripts/setJson.py -s versions.-1.install_size=$$( find build/pcm-kikit -type f -exec ls -la {} + | tr -s ' ' | cut -f5 -d' ' | paste -s -d+ - | bc ) \
		build/pcm-kikit/metadata.json build/pcm-kikit/metadata.json
	cd build/pcm-kikit && zip ../pcm-kikit.zip -r *
	cp build/pcm-kikit/metadata.json build/pcm-kikit-metadata.json
	scripts/setJson.py \
		-s versions.-1.download_sha256=\"$$( sha256sum build/pcm-kikit.zip | cut -d' ' -f1)\" \
		-s versions.-1.download_size=$$( du -sb build/pcm-kikit.zip | cut -f1) \
		-s versions.-1.download_url=\"TBA\" \
		build/pcm-kikit-metadata.json build/pcm-kikit-metadata.json

pcm-lib: $(PCM_LIB_RESOURCES)
	rm -rf build/pcm-kikit-lib build/pcm-kikit-lib.zip
	mkdir -p build/pcm-kikit-lib
	mkdir -p build/pcm-kikit-lib/resources
	mkdir -p build/pcm-kikit-lib/symbols
	mkdir -p build/pcm-kikit-lib/footprints
	cp -r pcm/kikit-lib/* build/pcm-kikit-lib
	cp kikit/resources/graphics/kikitIcon_64x64.png build/pcm-kikit-lib/resources/icon.png
	cp -r kikit/resources/kikit.pretty build/pcm-kikit-lib/footprints
	cp -r kikit/resources/kikit.kicad_sym build/pcm-kikit-lib/symbols
	scripts/setJson.py -s versions.-1.install_size=$$(find build/pcm-kikit-lib -type f -exec ls -la {} + | tr -s ' ' | cut -f5 -d' ' | paste -s -d+ - | bc) \
		build/pcm-kikit-lib/metadata.json build/pcm-kikit-lib/metadata.json
	cd build/pcm-kikit-lib && zip ../pcm-kikit-lib.zip -r *
	cp build/pcm-kikit-lib/metadata.json build/pcm-kikit-lib-metadata.json
	scripts/setJson.py \
		-s versions.-1.download_sha256=\"$$( sha256sum build/pcm-kikit-lib.zip | cut -d' ' -f1)\" \
		-s versions.-1.download_size=$$( du -sb build/pcm-kikit-lib.zip | cut -f1) \
		-s versions.-1.download_url=\"TBA\" \
		build/pcm-kikit-lib-metadata.json build/pcm-kikit-lib-metadata.json

docker-release:
	docker build -t yaqwsx/kikit:$(shell git describe --tags --always)-KiCAD8 --build-arg="KICAD_VERSION=8.0" .
	docker build -t yaqwsx/kikit:latest --build-arg="KICAD_VERSION=8.0" .
	docker build -t yaqwsx/kikit:$(shell git describe --tags --always)-KiCAD7 --build-arg="KICAD_VERSION=7.0" .

clean:
	rm -rf dist build
