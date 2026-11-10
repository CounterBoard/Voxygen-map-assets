export default {
  async fetch() {
    return new Response("Voxygen map assets are served as static assets.", {
      status: 404,
      headers: { "content-type": "text/plain; charset=utf-8" }
    });
  }
};
