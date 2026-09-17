import { expect, test } from './fixtures';

// No Search UI exists anywhere in the frontend (documented
// N/A-through-UI). GET /api/v1/search is real and verified directly.
test.describe('11 search - no UI; real backend endpoint verified directly', () => {
  test('a real project is findable by name via the real search endpoint', async ({ request }) => {
    const slug = `search-probe-${Date.now()}`;
    const created = await request.post('http://127.0.0.1:8000/api/v1/projects', {
      data: { name: 'SearchableUniqueProjectName', slug },
    });
    expect(created.ok()).toBe(true);

    const searchResponse = await request.get('http://127.0.0.1:8000/api/v1/search', {
      params: { q: 'SearchableUniqueProjectName' },
    });
    expect(searchResponse.ok()).toBe(true);
    const results = await searchResponse.json();
    expect(results.total).toBeGreaterThanOrEqual(1);
  });

  test('an empty query is rejected (422), not silently ignored', async ({ request }) => {
    const response = await request.get('http://127.0.0.1:8000/api/v1/search', { params: { q: '' } });
    expect(response.status()).toBe(422);
  });

  test('a query with no matches returns an empty, well-formed result set', async ({ request }) => {
    // Avoid any real English word (e.g. "no", "match") that could
    // coincidentally token-collide with this suite's own synthetic
    // fixture names (many contain words like "no-contrib") - a single
    // nonsense token has no plausible overlap with any real document.
    const response = await request.get('http://127.0.0.1:8000/api/v1/search', {
      params: { q: 'qqqxyzzynonexistentzzqq999888777' },
    });
    expect(response.ok()).toBe(true);
    const body = await response.json();
    expect(body.items).toEqual([]);
    expect(body.total).toBe(0);
  });
});
