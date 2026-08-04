import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { fetchArtifact } from "../api";

export default function ModelViewer({ jobId }: { jobId: string }) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x11151c);

    const camera = new THREE.PerspectiveCamera(45, mount.clientWidth / Math.max(1, mount.clientHeight), 0.1, 2000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.HemisphereLight(0xffffff, 0x3a4460, 1.1));
    const dir = new THREE.DirectionalLight(0xffffff, 1.6);
    dir.position.set(60, 80, 40);
    scene.add(dir);

    let geometry: THREE.BufferGeometry | null = null;
    let frame = 0;
    let disposed = false;

    (async () => {
      try {
        const data = await fetchArtifact(jobId, "model");
        if (disposed) return;
        const geo = new STLLoader().parse(data);
        geometry = geo;
        const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0x7fb3ff, metalness: 0.3, roughness: 0.5, flatShading: true }));
        geo.computeVertexNormals();
        geo.computeBoundingBox();
        const box = geo.boundingBox!;
        const center = new THREE.Vector3();
        box.getCenter(center);
        mesh.position.sub(center);
        mesh.position.y += 0;
        scene.add(mesh);

        const size = new THREE.Vector3();
        box.getSize(size);
        const radius = Math.max(size.x, size.y, size.z) / 2 || 1;
        camera.position.set(radius * 2.4, radius * 1.7, radius * 2.4);
        camera.near = radius / 100;
        camera.far = radius * 100;
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.update();
        setLoading(false);
      } catch (err) {
        if (disposed) return;
        setLoading(false);
        setError(`Failed to load model: ${err instanceof Error ? err.message : String(err)}`);
      }
    })();

    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      geometry?.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, [jobId]);

  return (
    <div className="viewer">
      <div className="viewer-canvas" ref={mountRef} />
      {loading && <div className="viewer-overlay">Loading model…</div>}
      {error && <div className="viewer-overlay error">{error}</div>}
    </div>
  );
}
