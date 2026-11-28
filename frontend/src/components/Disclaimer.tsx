export default function Disclaimer({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs text-mute ${className}`}>
      DermAI provides AI-assisted image analysis for screening and research. It is not a medical diagnosis. Consult a qualified
      healthcare professional about any skin concern.
    </p>
  );
}

