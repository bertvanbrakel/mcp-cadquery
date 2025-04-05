"""
Part: L-Bracket
Description: A simple L-shaped bracket.
Tags: bracket, metal, structural
Author: Roo
"""
import cadquery as cq

# L-bracket shape
result = (
    cq.Workplane("XY")
    .hLine(20)
    .vLine(20)
    .hLine(-5)
    .vLine(-15)
    .hLine(-15)
    .close()
    .extrude(5)
)

show_object(result)