import { useEffect, useState } from "react";
import { api } from "../api";

/** Renders a protected image by fetching it with the auth header into a blob URL. */
export default function AuthImage({
  path,
  alt,
  className,
  onClick,
}: {
  path: string;
  alt: string;
  className?: string;
  onClick?: () => void;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    api
      .fetchBlobUrl(path)
      .then((u) => {
        objectUrl = u;
        if (active) setUrl(u);
        else URL.revokeObjectURL(u);
      })
      .catch(() => {});
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  if (!url) return <div className={`img-skel ${className ?? ""}`} />;
  return <img src={url} alt={alt} className={className} onClick={onClick} />;
}
