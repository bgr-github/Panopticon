import { useEffect, useRef, useState } from "react";

const BASE_URL: string = "https://jsonplaceholder.typicode.com";

type Post = {
    id: number;
    title: string;
};

function Dashboard() {
    const [error, setError] = useState();
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [posts, setPosts] = useState<Post[]>([]);

    const abortControllerRef = useRef<AbortController | null>(null);

    useEffect(() => {
        const fetchPosts = async () => {
            abortControllerRef.current?.abort();
            abortControllerRef.current = new AbortController();

            setIsLoading(true);

            try {
                const response = await fetch(`${BASE_URL}/posts`, {
                    signal: abortControllerRef.current?.signal,
                });
                const posts: Post[] = await response.json();
                setPosts(posts);
            } catch (error: any) {
                if (error.name === "AbortError") {
                    console.log("Fetch aborted");
                    return;
                }
                setError(error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchPosts();

        return () => {
            abortControllerRef.current?.abort();
        };
    }, []);

    if (isLoading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div>Something went wrong. Please try again.</div>;
    }

    return (
        <div className="dashboard">
            <h1>Data Fething in React</h1>
            <ul>
                {posts.map((post) => (
                    <li key={post.id}>{post.title}</li>
                ))}
            </ul>
        </div>
    );
}

export default Dashboard;
