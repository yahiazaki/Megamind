export function Logo({ size = 36, withText = true }: { size?: number; withText?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <img src="/megamind-logo.svg" width={size} height={size} alt="" className="drop-shadow-sm" />
      {withText && <span className="text-lg font-extrabold tracking-tight text-brand-700 dark:text-brand-300">Megamind</span>}
    </span>
  );
}
