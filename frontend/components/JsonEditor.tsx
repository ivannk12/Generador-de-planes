"use client";

type Props = {
  value: string;
  onChange: (value: string) => void;
};

export default function JsonEditor({ value, onChange }: Props) {
  return (
    <textarea
      className="jsonEditor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      spellCheck={false}
    />
  );
}
