import { useEffect, useState } from "react";
import { fetchImageBlobUrl } from "../lib/api";

export default function AuthedImage({ id, variant, alt, className = "" }: { id: number; variant: "original" | "processed" | "lesion" | "cam" | "saliency"; alt: string; className?: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    fetchImageBlobUrl(id, variant)
      .then((u) => { if (cancelled) URL.revokeObjectURL(u); else { revoked = u; setUrl(u); } })
      .catch(() => setFailed(true));
    return () => { cancelled = true; if (revoked) URL.revokeObjectURL(revoked); };
  }, [id, variant]);
  if (failed) return <div className={`flex items-center justify-center bg-canvas text-xs text-mute ${className}`}>Not available</div>;
  if (!url) return <div className={`animate-pulse bg-canvas ${className}`} aria-label="Loading image" />;
  return <img src={url} alt={alt} className={`object-cover ${className}`} />;
}

