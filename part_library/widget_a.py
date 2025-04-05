"""
Part: Widget A
Description: A mounting widget with 2 holes.
Tags: widget, mounting, metal
Author: Roo
"""
import cadquery as cq

# A slightly more complex shape
result = (
    cq.Workplane("XY")
    .box(30, 20, 5)
    .faces(">Z")
    .workplane()
    .pushPoints([(-10, 0), (10, 0)])
    .circle(3)
    .cutThruAll()
)

show_object(result)