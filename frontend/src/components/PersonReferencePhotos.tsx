import { useEffect, useRef, useState } from "react";
import { CircleNotch, ImageSquare, LockKey, UploadSimple, UserCircle } from "@phosphor-icons/react";

import { getReferencePhotos, getStoredToken, referencePhotoUrl, uploadReferencePhoto } from "../api";

type ReferencePhoto = {
  id: string;
  entity_id: string;
  evidence_id: string;
  label: string;
  notes: string;
  created_at: string;
};

type PersonReferencePhotosProps = {
  entityId: string;
  entityName: string;
  canEdit: boolean;
};

/**
 * Profile photos are stored for human review and record keeping only.
 * They are never used for automated face matching.
 */
export default function PersonReferencePhotos({ entityId, entityName, canEdit }: PersonReferencePhotosProps) {
  const [photos, setPhotos] = useState<ReferencePhoto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [label, setLabel] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);
  const token = getStoredToken() ?? "";

  const load = async () => {
    try {
      setPhotos(await getReferencePhotos(entityId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Reference photos could not be loaded.");
    }
  };

  useEffect(() => {
    void load();
  }, [entityId]);

  const submit = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose an image file first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await uploadReferencePhoto(entityId, file, label.trim() || "Reference photo", "");
      if (fileRef.current) fileRef.current.value = "";
      setLabel("");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Reference photo upload failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="detail-section reference-photo-section">
      <span className="detail-label"><UserCircle size={13} /> Reference photos</span>
      <p className="reference-photo-note"><LockKey size={12} /> Stored for human review of {entityName}. Never used for automated face matching.</p>
      {error && <p className="reference-photo-error">{error}</p>}
      {photos.length > 0 ? (
        <div className="reference-photo-grid">
          {photos.map((photo) => (
            <figure key={photo.id} className="reference-photo">
              <img src={referencePhotoUrl(entityId, photo.id, token)} alt={`${photo.label} reference photo`} />
              <figcaption>{photo.label}<span>{new Date(photo.created_at).toLocaleString()}</span></figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <p className="reference-photo-empty"><ImageSquare size={14} /> No reference photos stored for this record.</p>
      )}
      {canEdit && (
        <div className="reference-photo-upload">
          <input className="text-input" placeholder="Photo label (optional)" value={label} onChange={(event) => setLabel(event.target.value)} />
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" aria-label="Reference photo file" />
          <button className="secondary-button compact" type="button" onClick={() => void submit()} disabled={busy}>
            {busy ? <CircleNotch className="spin" size={14} /> : <UploadSimple size={14} />} Add photo
          </button>
        </div>
      )}
    </div>
  );
}
