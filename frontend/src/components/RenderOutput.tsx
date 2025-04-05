import React from 'react';

// Define prop types
interface RenderOutputProps {
  renderUrl: string | null; // Renamed prop
}

const RenderOutput: React.FC<RenderOutputProps> = ({ renderUrl }) => { // Use renamed prop
  console.log("[RenderOutput] Rendering. renderUrl:", renderUrl); // Update log
  return (
    <div className="card">
      <h2>Rendered Output</h2>
      {renderUrl ? ( // Use renamed prop
        <img src={renderUrl} alt="Latest Rendered Output" style={{ maxWidth: '100%', border: '1px solid #ccc' }} />
      ) : (
        <p>No image rendered yet. Type in the script area to trigger auto-render.</p>
      )}
    </div>
  );
};

export default RenderOutput;