import chromadb
import argparse

def inspect_chroma_db(collection_name=None):
    """
    Connects to the persistent ChromaDB and prints its contents.
    If a collection_name is provided, it will only inspect that collection.
    """
    try:
        # Connect to the same persistent client
        client = chromadb.PersistentClient(path="./chroma_data")
        
        print("--- ChromaDB Inspector ---")
        
        collections = client.list_collections()
        if not collections:
            print("No collections found in the database.")
            return

        print(f"Found {len(collections)} collections: {[c.name for c in collections]}\n")

        for collection in collections:
            if collection_name and collection.name != collection_name:
                continue
            print(f"--- Inspecting Collection: '{collection.name}' ---")
            data = collection.get(include=["metadatas", "documents"]) # Get documents and their metadata
            count = collection.count()
            print(f"Total documents: {count}\n")
            for i, doc in enumerate(data.get('documents', [])):
                print(f"  Document {i+1} (ID: {data['ids'][i]}):")
                print(f"    Metadata: {data['metadatas'][i]}")
                print(f"    Content: '{doc[:200].replace(chr(10), ' ')}...'\n")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect ChromaDB.")
    parser.add_argument("-c", "--collection", help="The name of the collection to inspect.")
    args = parser.parse_args()
    inspect_chroma_db(args.collection)