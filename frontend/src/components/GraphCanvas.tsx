import { ArrowsOut, DownloadSimple, Minus, Plus, ShareNetwork } from "@phosphor-icons/react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { GraphEdge, GraphNode, GraphResponse } from "../types";

type GraphCanvasProps = {
  graph: GraphResponse;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onSelectNode: (node: GraphNode) => void;
  onSelectEdge: (edge: GraphEdge) => void;
};

const colors: Record<string, { fill: string; stroke: string; label: string }> = {
  CONFIRMED: { fill: "#b95d62", stroke: "#f0a0a0", label: "Source status" },
  CHARGED: { fill: "#bd7a42", stroke: "#f1bb72", label: "Recorded status" },
  ATTENTION: { fill: "#8e7941", stroke: "#e3c66e", label: "Analytical review" },
  RELEVANT: { fill: "#3b7180", stroke: "#71e0cf", label: "Relevant association" },
  UNKNOWN: { fill: "#4a5961", stroke: "#8b9ba4", label: "Unknown / unresolved" },
};

function nodeColor(node: GraphNode) {
  const normalized = node.status.toUpperCase();
  if (normalized.includes("CONFIRM")) return colors.CONFIRMED;
  if (normalized.includes("CHARG") || normalized.includes("INVESTIG")) return colors.CHARGED;
  if (normalized.includes("ATTENTION") || normalized.includes("REVIEW")) return colors.ATTENTION;
  if (normalized.includes("RELEVANT")) return colors.RELEVANT;
  return colors.UNKNOWN;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function GraphCanvas({ graph, selectedNodeId, selectedEdgeId, onSelectNode, onSelectEdge }: GraphCanvasProps) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const nodeDragRef = useRef<{ id: string; x: number; y: number } | null>(null);
  const width = 920;
  const height = 570;

  const computedPositions = useMemo(() => {
    const map = new Map<string, { x: number; y: number; depth: number }>();
    if (!graph.nodes.length) return map;
    const adjacency = new Map<string, string[]>();
    graph.edges.forEach((edge) => {
      adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target]);
      adjacency.set(edge.target, [...(adjacency.get(edge.target) ?? []), edge.source]);
    });
    const center = graph.center_id && graph.nodes.some((node) => node.id === graph.center_id) ? graph.center_id : graph.nodes[0].id;
    const depthMap = new Map<string, number>([[center, 0]]);
    const queue = [center];
    while (queue.length) {
      const current = queue.shift()!;
      const currentDepth = depthMap.get(current) ?? 0;
      (adjacency.get(current) ?? []).forEach((neighbor) => {
        if (!depthMap.has(neighbor)) {
          depthMap.set(neighbor, currentDepth + 1);
          queue.push(neighbor);
        }
      });
    }
    const groups = new Map<number, string[]>();
    graph.nodes.forEach((node) => {
      const depth = depthMap.get(node.id) ?? 2;
      groups.set(depth, [...(groups.get(depth) ?? []), node.id]);
    });
    groups.forEach((ids, depth) => {
      if (depth === 0) {
        map.set(ids[0], { x: width / 2, y: height / 2, depth });
        return;
      }
      const radius = Math.min(125 + depth * 85, 245);
      ids.forEach((id, index) => {
        const angle = (Math.PI * 2 * index) / ids.length - Math.PI / 2;
        map.set(id, { x: width / 2 + Math.cos(angle) * radius, y: height / 2 + Math.sin(angle) * radius, depth });
      });
    });
    return map;
  }, [graph]);
  const [positions, setPositions] = useState<Map<string, { x: number; y: number; depth: number }>>(computedPositions);

  useEffect(() => {
    setPositions(computedPositions);
  }, [computedPositions]);

  const startNodeDrag = (event: React.PointerEvent<SVGGElement>, node: GraphNode) => {
    event.stopPropagation();
    const position = positions.get(node.id);
    if (!position) return;
    nodeDragRef.current = { id: node.id, x: event.clientX, y: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
    onSelectNode(node);
  };

  const movePointer = (event: React.PointerEvent<SVGSVGElement>) => {
    if (nodeDragRef.current) {
      const current = nodeDragRef.current;
      const position = positions.get(current.id);
      if (position) {
        setPositions((previous) => {
          const next = new Map(previous);
          next.set(current.id, { ...position, x: position.x + (event.clientX - current.x) / zoom, y: position.y + (event.clientY - current.y) / zoom });
          return next;
        });
        nodeDragRef.current = { ...current, x: event.clientX, y: event.clientY };
      }
      return;
    }
    if (!dragRef.current) return;
    setPan({ x: dragRef.current.panX + event.clientX - dragRef.current.x, y: dragRef.current.panY + event.clientY - dragRef.current.y });
  };

  const startPan = (event: React.PointerEvent<SVGSVGElement>) => {
    dragRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const endPan = () => {
    dragRef.current = null;
    nodeDragRef.current = null;
  };

  const focusSelected = () => {
    if (!selectedNodeId) return;
    const position = positions.get(selectedNodeId);
    if (position) setPan({ x: width / 2 - position.x * zoom, y: height / 2 - position.y * zoom });
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const exportSvg = () => {
    const svg = document.querySelector<SVGSVGElement>(".graph-canvas");
    if (!svg) return;
    const copy = svg.cloneNode(true) as SVGSVGElement;
    copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const blob = new Blob([new XMLSerializer().serializeToString(copy)], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "signal-atlas-network.svg";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="graph-canvas-wrap">
      <div className="graph-toolbar">
        <div className="graph-toolbar-label"><ShareNetwork size={16} /><span>{graph.nodes.length} nodes</span><span className="toolbar-separator">/</span><span>{graph.edges.length} links</span></div>
        <div className="graph-controls">
          <button type="button" onClick={() => setZoom((value) => Math.min(1.5, value + 0.1))} aria-label="Zoom in"><Plus size={15} /></button>
          <button type="button" onClick={() => setZoom((value) => Math.max(0.6, value - 0.1))} aria-label="Zoom out"><Minus size={15} /></button>
          <button type="button" onClick={focusSelected} aria-label="Focus selected node" disabled={!selectedNodeId}><ShareNetwork size={15} /></button>
          <button type="button" onClick={resetView} aria-label="Reset graph view"><ArrowsOut size={15} /></button>
          <button type="button" onClick={exportSvg} aria-label="Export graph as SVG"><DownloadSimple size={15} /></button>
        </div>
      </div>
      <svg
        className="graph-canvas"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Interactive network graph"
        onPointerDown={startPan}
        onPointerMove={movePointer}
        onPointerUp={endPan}
        onPointerCancel={endPan}
      >
        <defs>
          <pattern id="graph-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(185,211,218,.055)" strokeWidth="1" />
          </pattern>
          <marker id="edge-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#6b7e86" />
          </marker>
        </defs>
        <rect width={width} height={height} fill="url(#graph-grid)" />
        <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
          {graph.edges.map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            const active = selectedEdgeId === edge.id;
            return (
              <g key={edge.id} className={`graph-edge ${active ? "selected" : ""}`} onClick={(event) => { event.stopPropagation(); onSelectEdge(edge); }}>
                <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} markerEnd="url(#edge-arrow)" />
                <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 5}>{edge.relationship_type.replaceAll("_", " ")}</text>
              </g>
            );
          })}
          {graph.nodes.map((node) => {
            const position = positions.get(node.id);
            if (!position) return null;
            const color = nodeColor(node);
            const selected = selectedNodeId === node.id;
            const radius = Math.min(24, 13 + node.degree * 1.4);
            return (
              <g key={node.id} className={`graph-node ${selected ? "selected" : ""}`} transform={`translate(${position.x} ${position.y})`} onPointerDown={(event) => startNodeDrag(event, node)} onClick={(event) => { event.stopPropagation(); onSelectNode(node); }}>
                {selected && <circle r={radius + 8} className="node-halo" />}
                <circle r={radius} fill={color.fill} stroke={selected ? "#d8fff7" : color.stroke} strokeWidth={selected ? 2.5 : 1.5} />
                <text className="node-initials" y="4">{initials(node.name)}</text>
                <text className="node-label" y={radius + 17}>{node.name.length > 20 ? `${node.name.slice(0, 19)}…` : node.name}</text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="graph-legend">
        <span><i className="legend-swatch source" />Source status</span>
        <span><i className="legend-swatch review" />Analytical review</span>
        <span><i className="legend-swatch relevant" />Relevant association</span>
        <span><i className="legend-swatch unknown" />Unknown</span>
      </div>
    </div>
  );
}

export default GraphCanvas;
