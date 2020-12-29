#!/usr/bin/env bats

load common

@test "Present a single board" {
    echo "This is the page contents!" > boardReadme.md
    kikit present boardpage \
        -d boardReadme.md \
        --name "TestBoard" \
        --repository 'https://github.com/yaqwsx/KiKit' \
        web
}
