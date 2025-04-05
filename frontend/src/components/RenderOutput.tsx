import React, { Suspense } from 'react'; // Import Suspense
import { Canvas, useLoader } from '@react-three/fiber';
import { OrbitControls, Center } from '@react-three/drei';
import * as THREE from 'three';

// Define prop types
interface RenderOutputProps {
  renderDataUrl: string | null; // Expect URL to TJS JSON file
}

// Helper component to load and display the TJS model
function Model({ url }: { url: string }) {
  // Note: TJS is essentially a scene graph JSON.
  // We use ObjectLoader to parse it.
  const scene = useLoader(THREE.ObjectLoader, url);
  console.log("[Model] Loaded scene data from:", url, scene);

  // The loader returns a Group or Scene object. We need to add it to our scene.
  // We also might need to adjust its position/scale depending on how it was exported.
  return (
     <primitive object={scene} scale={0.1} /> // Add the loaded scene graph, scale down if needed
  );
}

const RenderOutput: React.FC<RenderOutputProps> = ({ renderDataUrl }) => {
  console.log("[RenderOutput] Rendering. renderDataUrl:", renderDataUrl);
  return (
    <div className="card">
      <h2>Rendered Output</h2>
      <div style={{ height: '400px', border: '1px solid #ccc', background: '#f0f0f0' }}> {/* Increased height */}
        {renderDataUrl ? (
          <Canvas camera={{ position: [50, 50, 50], fov: 35 }}> {/* Adjusted camera */}
             <color attach="background" args={['#f0f0f0']} /> {/* Match background */}
             <ambientLight intensity={Math.PI} /> {/* Increased ambient light */}
             <pointLight position={[100, 100, 100]} decay={0} intensity={Math.PI} />
             <pointLight position={[-100, -100, -100]} decay={0} intensity={Math.PI*0.5} />
             <Suspense fallback={<p style={{textAlign: 'center', paddingTop: '20px'}}>Loading model...</p>}>
                <Center> {/* Center the loaded model */}
                    <Model url={renderDataUrl} />
                </Center>
             </Suspense>
             <OrbitControls />
          </Canvas>
        ) : (
          <p style={{ textAlign: 'center', paddingTop: '20px' }}>No model rendered yet. Type in the script area to trigger auto-render.</p>
        )}
      </div>
    </div>
  );
};

export default RenderOutput;