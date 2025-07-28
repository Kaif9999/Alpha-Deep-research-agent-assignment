import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Alpha Platform Research Agent',
  description: 'Automated company research and data enrichment platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="container">
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
