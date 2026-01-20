export function generateSessionId(): string {
  const stamp = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 6);
  return `td-${stamp}-${random}`;
}
