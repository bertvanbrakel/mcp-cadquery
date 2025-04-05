"""
Part: Simple Cube
Description: A basic 10x10x10 cube centered on the origin.
Tags: cube, basic, example
Author: Roo
"""
import cadquery as cq

# --- Parameters (Optional) ---
# size = 10.0

# --- Part Logic ---
# Create the cube
cube = cq.Workplane("XY").box(10, 10, 10)

# Use show_object so the scanner can find the result
show_object(cube)