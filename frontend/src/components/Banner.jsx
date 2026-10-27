import { SOURCE_LABEL } from "../format.js";

export default function Banner({ metrics, quality }) {
  if (metrics.authoritative) {
    return (
      <div className="banner ok" role="status">
        <strong>{SOURCE_LABEL[quality.data_source]}.</strong> Coverage meets the configured threshold. The day-ahead cutoff is still an
        assumption, so treat results as indicative until it is confirmed.
      </div>
    );
  }
  return (
    <div className="banner warn" role="alert">
      <strong>Not authoritative.</strong> {metrics.not_authoritative_reasons.join(" ")}
      {quality.notes.length > 0 && <div className="banner-note">{quality.notes.join(" ")}</div>}
    </div>
  );
}
