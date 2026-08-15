__version__ = "0.3.0"


from aiohttp import web
from aiohttp.web_urldispatcher import (
    AbstractResource,
    UrlDispatcher,
    UrlMappingMatchInfo,
)


class FastUrlDispatcher(UrlDispatcher):
    """UrlDispatcher that uses a dict lookup for resolving."""

    def __init__(self) -> None:
        """Initialize the dispatcher."""
        super().__init__()
        self._resource_index: dict[str, list[AbstractResource]] = {}

    def register_resource(self, resource: AbstractResource) -> None:
        """Register a resource."""
        super().register_resource(resource)
        canonical = resource.canonical.partition("{")[0].rstrip("/") or "/"
        # There may be multiple resources for a canonical path
        # so we use a list to avoid falling back to a full linear search
        self._resource_index.setdefault(canonical, []).append(resource)

    async def resolve(self, request: web.Request) -> UrlMappingMatchInfo:
        """Resolve a request."""
        resource_index = self._resource_index
        # Walk the url parts looking for candidates. We walk the url backwards
        # to ensure the most explicit match is found first. If there are multiple
        # candidates for a given url part because there are multiple resources
        # registered for the same canonical path, we resolve them in a linear
        # fashion to ensure registration order is respected.
        url_part = request.rel_url.raw_path
        while url_part:  # pragma: no branch
            for candidate in resource_index.get(url_part, ()):
                if (match_dict := (await candidate.resolve(request))[0]) is not None:
                    return match_dict
            if url_part == "/":
                break
            url_part = url_part.rpartition("/")[0] or "/"

        # Finally, fallback to the linear search
        return await super().resolve(request)


def attach_fast_url_dispatcher(
    app: web.Application, dispatcher: FastUrlDispatcher
) -> None:
    """Attach the fast url dispatcher to the app."""
    app._router = dispatcher
