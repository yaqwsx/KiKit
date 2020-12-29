#!/usr/bin/env bats

load common

@test "Hide references" {
    cp $RES/conn.kicad_pcb conn-hidden.kicad_pcb
    kikit modify references --hide -p '.*' conn-hidden.kicad_pcb
}
