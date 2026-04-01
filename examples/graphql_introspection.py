"""Example usage of GraphQL introspection client.

This example demonstrates how to use the GraphQLIntrospector to
extract schema information from a GraphQL API.
"""

import asyncio
from dietmcp.graphql import GraphQLIntrospector


async def main():
    """Introspect a GraphQL API and print schema information."""
    introspector = GraphQLIntrospector(timeout=30.0)

    # Example with a public GraphQL API
    url = "https://graphqlzero.almansi.me/api"

    try:
        schema = await introspector.introspect(url)

        print(f"Schema introspection complete!")
        print(f"Total types: {schema.total_types}")
        print(f"Queries: {len(schema.queries)}")
        print(f"Mutations: {len(schema.mutations)}")
        print(f"Has queries: {schema.has_queries}")
        print(f"Has mutations: {schema.has_mutations}")

        # Print first 5 queries
        print("\n=== Sample Queries ===")
        for query in schema.queries[:5]:
            print(f"\n{query.name}")
            if query.description:
                print(f"  Description: {query.description}")
            print(f"  Return type: {query.field.type_name}")
            if query.field.args:
                print(f"  Arguments:")
                for arg in query.field.args:
                    default = f" = {arg.default_value}" if arg.default_value else ""
                    print(f"    - {arg.name}: {arg.type_name}{default}")

        # Print first 5 mutations (if any)
        if schema.has_mutations:
            print("\n=== Sample Mutations ===")
            for mutation in schema.mutations[:5]:
                print(f"\n{mutation.name}")
                if mutation.description:
                    print(f"  Description: {mutation.description}")
                print(f"  Return type: {mutation.field.type_name}")
                if mutation.field.args:
                    print(f"  Arguments:")
                    for arg in mutation.field.args:
                        default = f" = {arg.default_value}" if arg.default_value else ""
                        print(f"    - {arg.name}: {arg.type_name}{default}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
