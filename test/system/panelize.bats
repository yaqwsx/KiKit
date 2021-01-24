#!/usr/bin/env bats

load common

@test "Extract board" {
    kikit panelize extractboard \
        --sourcearea 100 50 100 100 \
        $RES/conn.kicad_pcb extract_res.kicad_pcb
}

@test "Simple grid, no space, vcuts" {
    kikit panelize grid \
        --gridsize 2 2 \
        --vcuts \
        $RES/conn.kicad_pcb panel1.kicad_pcb
}

@test "Simple grid, no space, mousebites" {
    kikit panelize grid \
        --gridsize 2 2 \
        --mousebites 0.5 1 0 \
        $RES/conn.kicad_pcb panel2.kicad_pcb
}

@test "Simple grid, no space, mousebites with radius" {
    kikit panelize grid \
        --gridsize 2 2 \
        --mousebites 0.5 1 0 \
        --radius 1 \
        $RES/conn.kicad_pcb panel3.kicad_pcb
}

@test "Simple grid, with space, vcusts and radius" {
    kikit panelize grid \
        --space 3 --gridsize 2 2 \
        --tabwidth 18 --tabheight 10 \
        --vcuts \
        --radius 1 \
        $RES/conn.kicad_pcb panel4.kicad_pcb
}

@test "Simple grid, with space, mousebites, multiple tabs and radius" {
    kikit panelize grid \
        --space 3 --gridsize 2 2 \
        --tabwidth 3 --tabheight 3 --htabs 1 --vtabs 2 \
        --mousebites 0.5 1 0.25 \
        --radius 1 \
        $RES/conn.kicad_pcb panel5.kicad_pcb
}

@test "Simple grid, with space, vcuts, rails, tooling and fiducials" {
    kikit panelize grid \
        --space 3 --gridsize 2 2 \
        --tabwidth 18 --tabheight 10 \
        --vcuts --radius 1 \
        --railsTb 5 --fiducials 10 2.5 1 2 --tooling 5 2.5 1.5 \
        $RES/conn.kicad_pcb panel6.kicad_pcb
}

@test "Simple grid with frame, tooling and fiducials" {
    kikit panelize grid \
        --space 3 --gridsize 2 2 \
        --tabwidth 5 --tabheight 5 \
        --mousebites 0.5 1 0 \
        --radius 1 \
        --panelsize 75 58 --framecutH \
        --fiducials 10 2.5 1 2 --tooling 5 2.5 1.5 \
        $RES/conn.kicad_pcb panel7.kicad_pcb
}

@test "Tightgrid" {
    kikit panelize tightgrid \
        --slotwidth 2.5 --space 8 --gridsize 2 2 \
        --tabwidth 15 --tabheight 8 \
        --mousebites 0.5 1 0.25 \
        --radius 1 --panelsize 80 60 \
        $RES/conn.kicad_pcb panel8.kicad_pcb
}

@test "Grid with board rotation" {
    kikit panelize grid \
        --space 2 --gridsize 2 2 \
        --tabwidth 3 --tabheight 3 \
        --mousebites 0.5 1 0.25 \
        --radius 1 --panelsize 80 80 --rotation 45 \
        $RES/conn.kicad_pcb panel9.kicad_pcb
}

@test "Grid with alternation" {
    kikit panelize grid \
        --space 2 --gridsize 2 2 \
        --tabwidth 3 --tabheight 3 \
        --mousebites 0.5 1 0.25 \
        --radius 1 --panelsize 80 80 --alternation rows \
        $RES/conn.kicad_pcb panel-alternationRows.kicad_pcb
    kikit panelize grid \
        --space 2 --gridsize 2 2 \
        --tabwidth 3 --tabheight 3 \
        --mousebites 0.5 1 0.25 \
        --radius 1 --panelsize 80 80 --alternation cols \
        $RES/conn.kicad_pcb panel-alternationCols.kicad_pcb
    kikit panelize grid \
        --space 2 --gridsize 2 2 \
        --tabwidth 3 --tabheight 3 \
        --mousebites 0.5 1 0.25 \
        --radius 1 --panelsize 80 80 --alternation rowsCols \
        $RES/conn.kicad_pcb panel-alternationRowsCols.kicad_pcb
}

@test "Tightgrid with custom tab positions" {
    kikit panelize tightgrid \
        --slotwidth 2.5 --space 8 --gridsize 2 2 \
        --htabs 0 --vtabs 0 --tabsfrom Eco2.User 3 --tabsfrom Eco1.User 5 \
        --mousebites 0.5 1 0.25 \
        --radius 1 --panelsize 80 80 \
        $RES/conn.kicad_pcb panel10.kicad_pcb
}

@test "Copper fill" {
    kikit panelize grid \
        --space 3 --gridsize 2 2 \
        --tabwidth 18 --tabheight 10 \
        --vcuts --radius 1 --panelsize 70 55 --copperfill \
        $RES/conn.kicad_pcb panel11.kicad_pcb
}