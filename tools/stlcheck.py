# STL check (freecadcmd tools/stlcheck.py): size, isSolid and facet count of cad/case_base.stl and cad/case_lid.stl.
import Mesh
for n in ("case_base","case_lid"):
    m=Mesh.Mesh(__import__("os").path.join(__import__("os").getcwd(), "cad", "%s.stl")%n); b=m.BoundBox
    print(n, round(b.XLength,1), round(b.YLength,1), round(b.ZLength,1), "zmin", round(b.ZMin,2), "solid", m.isSolid(), "facets", m.CountFacets)
