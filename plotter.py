from typing import Tuple
import svgwrite

class Plotter():
    def __init__(self, size:Tuple[int, int], bottom_left_coords:Tuple[float, float], top_right_coords:Tuple[float, float]) -> None:
        self.d = svgwrite.Drawing('untitled.svg', size=size, profile='full')
        self.size = size
        self.mins = bottom_left_coords
        self.maxs = top_right_coords

    def _proj(self, x: Tuple[float,float]) -> Tuple[float,float]:
        return (
            (x[0] - self.mins[0]) / (self.maxs[0] - self.mins[0]) * self.size[0],
            self.size[1] - (x[1] - self.mins[1]) / (self.maxs[1] - self.mins[1]) * self.size[1],
        )

    def line(self, a:Tuple[float,float], b:Tuple[float,float], thickness:float=1., color:Tuple[int,int,int]=(0,0,0), absolute:bool=False) -> None:
        if not absolute:
            a = self._proj(a)
            b = self._proj(b)
        self.d.add(self.d.line(a, b, stroke_width=thickness, stroke=svgwrite.rgb(*color)))

    def circle(self, pos:Tuple[float,float], radius:float=1., color:Tuple[int,int,int]=(0,0,0), absolute:bool=False) -> None:
        if not absolute:
            pos = self._proj(pos)
        self.d.add(self.d.circle(pos, r=radius, fill=svgwrite.rgb(*color)))

    def text(self, s:str, pos:Tuple[float,float], size:float=16, color:Tuple[int,int,int]=(0,0,0), absolute:bool=False) -> None:
        if not absolute:
            pos = self._proj(pos)
        self.d.add(self.d.text(s, insert=pos, fill=svgwrite.rgb(*color), style=f'font-size:{size}px; font-family:Arial'))

    def tostr(self) -> str:
        return '<?xml version="1.0" encoding="utf-8" ?>\n' + str(self.d.tostring())
