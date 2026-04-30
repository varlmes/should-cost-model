import base64
import html
import io
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from geometry.mesh_analyzer import MeshInputs, analyze_stl, demo_stl_bytes

st.set_page_config(page_title="3D Object Viewer", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
  .mesh-hero { background: radial-gradient(circle at 18% 20%, rgba(92,185,255,.9) 0, transparent 23%), linear-gradient(135deg, #111417 0%, #26353c 55%, #35422d 100%); color: #f1fbff; padding: 28px 32px; border: 1px solid rgba(255,255,255,.14); margin-bottom: 18px; }
  .mesh-kicker { letter-spacing: .18em; text-transform: uppercase; color: #bee9ff; font-size: .72rem; }
  .mesh-price { font-size: 3rem; line-height: 1; font-weight: 800; margin: 10px 0 6px; }
  .mesh-band { color: #def3ff; }
  .rule { border: none; border-top: 1px solid #d4d9dc; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float, currency: str) -> str:
    return f"{currency}{value:,.2f}"


def metric_rows(stats):
    return pd.DataFrame([
        ("Triangles", f"{stats.triangle_count:,}"),
        ("Width", f"{stats.width_mm / 10:,.2f} cm"),
        ("Depth", f"{stats.depth_mm / 10:,.2f} cm"),
        ("Height", f"{stats.height_mm / 10:,.2f} cm"),
        ("Volume", f"{stats.volume_cm3:,.2f} cm3"),
        ("Surface Area", f"{stats.surface_area_cm2:,.2f} cm2"),
        ("Weight", f"{stats.weight_g:,.2f} g"),
        ("Filament Length", f"{stats.filament_length_mm:,.0f} mm"),
        ("Build Time", f"{stats.build_hours} hr {stats.build_minutes} min"),
    ], columns=["Metric", "Value"])


def viewer_html(stl_data: bytes, filename: str) -> str:
    payload = base64.b64encode(stl_data).decode("ascii")
    safe_name = html.escape(filename)
    payload_json = json.dumps(payload)
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body {{ margin: 0; height: 100%; overflow: hidden; background: #15191d; font-family: Arial, sans-serif; }}
    #viewer {{ width: 100vw; height: 560px; position: relative; }}
    #hud {{ position: absolute; top: 12px; left: 12px; z-index: 2; color: #eef8ff; background: rgba(13,17,23,.68); border: 1px solid rgba(255,255,255,.16); padding: 10px 12px; font-size: 12px; line-height: 1.45; }}
    #hint {{ position: absolute; right: 12px; bottom: 12px; z-index: 2; color: #b8c7cf; background: rgba(13,17,23,.64); border: 1px solid rgba(255,255,255,.12); padding: 8px 10px; font-size: 12px; }}
    #error {{ display: none; position: absolute; inset: 0; z-index: 3; color: #f6fbff; background: #15191d; padding: 24px; box-sizing: border-box; }}
    #error strong {{ color: #ffcf75; }}
  </style>
  <script type="importmap">
    {{
      "imports": {{
        "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
        "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
      }}
    }}
  </script>
</head>
<body>
  <div id="viewer">
    <div id="hud"><strong>{safe_name}</strong><br/>Drag to orbit · scroll to zoom · right-drag to pan</div>
    <div id="hint">STL rendered with Three.js</div>
    <div id="error"><strong>3D viewer could not start.</strong><br/><span id="errorText"></span></div>
  </div>
  <script type="module">
    import * as THREE from "three";
    import {{ OrbitControls }} from "three/addons/controls/OrbitControls.js";
    import {{ STLLoader }} from "three/addons/loaders/STLLoader.js";

    try {{
      const container = document.getElementById("viewer");
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x15191d);

      const camera = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 0.1, 100000);
      const renderer = new THREE.WebGLRenderer({{ antialias: true }});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(container.clientWidth, container.clientHeight);
      container.appendChild(renderer.domElement);

      scene.add(new THREE.HemisphereLight(0xf5fbff, 0x1c2227, 2.4));
      const key = new THREE.DirectionalLight(0xffffff, 2.2);
      key.position.set(4, -6, 8);
      scene.add(key);

      const bytes = Uint8Array.from(atob({payload_json}), char => char.charCodeAt(0));
      const loader = new STLLoader();
      const geometry = loader.parse(bytes.buffer);
      geometry.computeVertexNormals();
      geometry.center();

      const material = new THREE.MeshStandardMaterial({{
        color: 0xd7edf7,
        roughness: 0.42,
        metalness: 0.08,
        side: THREE.DoubleSide
      }});
      const mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry, 30),
        new THREE.LineBasicMaterial({{ color: 0x31424a, transparent: true, opacity: 0.45 }})
      );
      scene.add(edges);

      const box = new THREE.Box3().setFromObject(mesh);
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z, 1);
      const grid = new THREE.GridHelper(maxDim * 1.35, 12, 0x49616b, 0x26343a);
      grid.rotation.x = Math.PI / 2;
      grid.position.z = box.min.z - maxDim * 0.03;
      scene.add(grid);

      camera.position.set(maxDim * 1.1, -maxDim * 1.55, maxDim * 0.9);
      camera.near = maxDim / 1000;
      camera.far = maxDim * 1000;
      camera.updateProjectionMatrix();

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.target.set(0, 0, 0);
      controls.update();

      function resize() {{
        const width = container.clientWidth;
        const height = container.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
      }}
      window.addEventListener("resize", resize);

      function animate() {{
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
      }}
      animate();
    }} catch (error) {{
      document.getElementById("errorText").textContent = error && error.message ? error.message : String(error);
      document.getElementById("error").style.display = "block";
    }}
  </script>
</body>
</html>
"""


st.markdown("#### — Sourcing Operations Suite")
st.title("3D Object Viewer")
st.caption("Inspect STL geometry and estimate print material, cost, and simple build time.")
st.markdown("Reference project: [lrusso/3DObjectViewer](https://github.com/lrusso/3DObjectViewer)")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

with st.form("mesh_viewer"):
    c1, c2 = st.columns([2, 1])
    uploaded = c1.file_uploader("Upload STL File", type=["stl"], help="STL files are analyzed locally. OBJ and 3DS can be converted to STL before upload.")
    currency = c2.text_input("Currency Symbol", value="$", max_chars=4)

    p1, p2, p3, p4 = st.columns(4)
    density = p1.number_input("Density (g/cc)", min_value=0.0, value=1.05, step=0.05)
    material_cost = p2.number_input("Material Cost / kg", min_value=0.0, value=200.0, step=5.0)
    filament_diameter = p3.number_input("Filament Diameter (mm)", min_value=0.01, value=1.75, step=0.05)
    print_speed = p4.number_input("Print Speed (mm/s)", min_value=0.01, value=150.0, step=5.0)
    submitted = st.form_submit_button("Analyze 3D Object", type="primary")

if submitted or "mesh_stats" not in st.session_state:
    try:
        file_bytes = uploaded.getvalue() if uploaded else demo_stl_bytes()
        file_name = uploaded.name if uploaded else "demo-object.stl"
        inputs = MeshInputs(
            density_g_cc=float(density),
            material_cost_per_kg=float(material_cost),
            filament_diameter_mm=float(filament_diameter),
            print_speed_mm_s=float(print_speed),
        )
        st.session_state["mesh_stats"] = analyze_stl(file_bytes, inputs)
        st.session_state["mesh_file_bytes"] = file_bytes
        st.session_state["mesh_file_name"] = file_name
        st.session_state["mesh_currency"] = currency or "$"
    except Exception as exc:
        st.error(f"3D object analysis failed: {exc}")

stats = st.session_state.get("mesh_stats")
file_bytes = st.session_state.get("mesh_file_bytes")
file_name = st.session_state.get("mesh_file_name", "object.stl")
currency = st.session_state.get("mesh_currency", "$")

if stats and file_bytes:
    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("Viewer")
    components.html(viewer_html(file_bytes, file_name), height=580, scrolling=False)

    st.subheader("Geometry & Print Estimate")
    st.markdown(
        f"""
<div class="mesh-hero">
  <div class="mesh-kicker">Estimated Print Cost</div>
  <div class="mesh-price">{money(stats.material_cost, currency)}</div>
  <div class="mesh-band">Weight: {stats.weight_g:,.2f} g | Volume: {stats.volume_cm3:,.2f} cm3 | Surface: {stats.surface_area_cm2:,.2f} cm2</div>
  <div class="mesh-band">Size: {stats.width_mm / 10:,.2f} x {stats.depth_mm / 10:,.2f} x {stats.height_mm / 10:,.2f} cm | Build time: {stats.build_hours} hr {stats.build_minutes} min</div>
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cols[0].metric("Volume", f"{stats.volume_cm3:,.2f} cm3")
    cols[1].metric("Weight", f"{stats.weight_g:,.2f} g")
    cols[2].metric("Material Cost", money(stats.material_cost, currency))
    cols[3].metric("Build Time", f"{stats.build_hours}h {stats.build_minutes}m")

    detail_df = metric_rows(stats)
    st.dataframe(detail_df, width="stretch", hide_index=True)
    for note in stats.notes:
        st.caption(f"- {note}")

    csv_buffer = io.StringIO()
    detail_df.to_csv(csv_buffer, index=False)
    st.download_button("Download 3D Object Estimate (.csv)", csv_buffer.getvalue(), file_name="3d_object_estimate.csv", mime="text/csv")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#76848b; margin-top:28px; border-top:1px solid #d4d9dc; padding-top:10px;">
  3D Object Viewer | STL viewport + dimensions + weight + material cost + simple print time | Inspired by lrusso/3DObjectViewer.
</div>
""",
    unsafe_allow_html=True,
)
