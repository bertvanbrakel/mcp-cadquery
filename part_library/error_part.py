"""
Part: Error Part
Description: This part intentionally causes an error.
Tags: error, test
Author: Roo
"""
import cadquery as cq

# Intentionally invalid operation
result = cq.Workplane("XY").box(1, 1, 0.1).edges(">Z").fillet(0.2)

show_object(result)