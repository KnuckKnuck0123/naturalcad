type TopbarProps = {
  brand: string;
  status: string;
};

export function Topbar({ brand, status }: TopbarProps) {
  return (
    <header className="topbar">
      <span className="topbar__brand">{brand}</span>
      <span className="topbar__status">{status}</span>
    </header>
  );
}
