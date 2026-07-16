"""Data model for a single scraped Scribd document."""
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class DocumentMetadata:
    book_name: str
    uploaded_by: Optional[str]
    page_numbers: Optional[str]
    likes: Optional[str]       # formatted like "83% (6)" - percentage + rating count
    views: Optional[str]       # formatted like "11K"
    description: Optional[str]
    book_url: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentMetadata":
        return cls(
            book_name=data.get("book_name"),
            uploaded_by=data.get("uploaded_by"),
            page_numbers=data.get("page_numbers"),
            likes=data.get("likes"),
            views=data.get("views"),
            description=data.get("description"),
            book_url=data["book_url"],
        )
