import React, { useState } from 'react';

function Recommend() {
  const [department, setDepartment] = useState('');
  const [gender, setGender] = useState('');
  const [age, setAge] = useState('');
  const [interests, setInterests] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResults([]);
    try {
      const payload = { department, gender, age, interests };
      const res = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data && Array.isArray(data.results)) {
        setResults(data.results);
      }
    } catch (err) {
      console.error('추천 요청 실패', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="recommend">
      <h2>개인화 추천</h2>
      <form className="recommend-form" onSubmit={handleSubmit}>
        <div className="form-row">
          <label>학과</label>
          <input value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="예: 소프트웨어학부" />
        </div>
        <div className="form-row">
          <label>성별</label>
          <input value={gender} onChange={(e) => setGender(e.target.value)} placeholder="예: 남 / 여" />
        </div>
        <div className="form-row">
          <label>나이</label>
          <input value={age} onChange={(e) => setAge(e.target.value)} placeholder="예: 23" />
        </div>
        <div className="form-row">
          <label>관심분야</label>
          <input value={interests} onChange={(e) => setInterests(e.target.value)} placeholder="예: 인턴십, 공모전, 장학금" />
        </div>
        <div className="form-row form-row-submit">
          <button className="recommend-submit" type="submit" disabled={loading}>
            {loading ? '추천 중...' : '추천받기'}
          </button>
        </div>
      </form>

      <div className="recommend-results">
        {results.map((item, idx) => (
          <a className="card" key={idx} href={item.link} target="_blank" rel="noreferrer">
            <div className="card-title">{item.title || '제목 없음'}</div>
            <div className="card-summary">{item.summary || ''}</div>
          </a>
        ))}
      </div>
    </div>
  );
}

export default Recommend;


